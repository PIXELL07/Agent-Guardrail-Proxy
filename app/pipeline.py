"""
Orchestrates the detection funnel.

Order of operations, and why:
  1. Regex        -- near-zero cost. If it fires, block immediately, skip
                     everything else.
  2. Similarity + classifier (run together) -- still cheap (no network
                     call). If EITHER fires with high confidence, block.
                     If both clearly say benign, allow -- no need to spend
                     money on the judge model.
  3. LLM judge    -- only reached when tiers 1-2 don't agree confidently
                     (e.g. similarity says maybe, classifier says no, or
                     both are in a mid-confidence band). This is the
                     expensive path, so it should be the minority of
                     traffic.

This ordering is what makes the "reduced judge-model calls by X%" resume
claim true rather than aspirational -- most requests never reach step 3.
"""

from __future__ import annotations

import time

from app.detectors.regex_detector import check_regex
from app.detectors.similarity_detector import SimilarityDetector
from app.detectors.classifier_detector import InjectionClassifier
from app.detectors.llm_judge import judge
from app.schemas import ToolCallPayload, InspectResponse, TierResult

# Confidence band: if both cheap tiers land inside this range, we're not
# confident enough to decide without the judge model.
#
# NOTE: this was originally 0.25, which caused a real bug -- plain,
# data-like tool arguments (e.g. "Acme Corp / 4500 / 2026-07-20") produced
# classifier confidence around 0.30 just from noise, well above the
# original 0.25 floor, so every ordinary tool call was being escalated to
# the (slow, costly) judge model. Raised to 0.35 based on the actual
# confidence distribution observed on benign vs. genuinely ambiguous text
# during testing.
AMBIGUOUS_LOW = 0.35
AMBIGUOUS_HIGH = 0.6


class DetectionPipeline:
    def __init__(self, judge_backend: str = "ollama"):
        # Fit the similarity/classifier models once at startup, not per request.
        self.similarity = SimilarityDetector()
        self.classifier = InjectionClassifier()
        self.judge_backend = judge_backend

    def _combined_text(self, payload: ToolCallPayload) -> str:
        """Flatten everything worth inspecting into one text blob."""
        parts = [str(v) for v in payload.arguments.values()]
        if payload.source_context:
            parts.append(payload.source_context)
        return "\n".join(parts)

    async def inspect(self, payload: ToolCallPayload) -> InspectResponse:
        start = time.perf_counter()
        text = self._combined_text(payload)
        tier_results: list[TierResult] = []

        # Tier 1: regex
        regex_result = check_regex(text)
        tier_results.append(regex_result)
        if regex_result.triggered:
            return self._finish(payload, tier_results, "block", regex_result, start)

        # Tier 2: similarity + classifier, run together
        sim_result = self.similarity.check(text)
        clf_result = self.classifier.classify(text)
        tier_results.extend([sim_result, clf_result])

        if sim_result.triggered or clf_result.triggered:
            triggering = sim_result if sim_result.triggered else clf_result
            return self._finish(payload, tier_results, "block", triggering, start)

        # Both tier-2 detectors confidently say benign -> allow without
        # paying for the judge model.
        if sim_result.confidence < AMBIGUOUS_LOW and clf_result.confidence < AMBIGUOUS_LOW:
            allow_result = TierResult(
                tier="similarity+classifier",
                triggered=False,
                confidence=max(sim_result.confidence, clf_result.confidence),
                reason="Both tier-2 detectors confidently scored this as benign",
            )
            return self._finish(payload, tier_results, "allow", allow_result, start)

        # Tier 3: ambiguous -- escalate to the judge model
        judge_result = await judge(text, backend=self.judge_backend)
        tier_results.append(judge_result)
        decision = "block" if judge_result.triggered else "allow"
        return self._finish(payload, tier_results, decision, judge_result, start)

    def _finish(
        self,
        payload: ToolCallPayload,
        tier_results: list[TierResult],
        decision: str,
        deciding_tier: TierResult,
        start: float,
    ) -> InspectResponse:
        latency_ms = (time.perf_counter() - start) * 1000
        return InspectResponse(
            decision=decision,
            triggered_tier=deciding_tier.tier if decision == "block" else None,
            confidence=deciding_tier.confidence,
            reason=deciding_tier.reason,
            tier_results=tier_results,
            latency_ms=latency_ms,
        )
