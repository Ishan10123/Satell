import json
import unittest

import httpx

from src.rag_pipeline.generation.claim_verifier import (
    VERIFIER_SYSTEM_PROMPT, LocalClaimVerifier, conservative_qwen_token_estimate,
)
from src.rag_pipeline.generation.errors import (
    ClaimVerifierConnectionFailure, ClaimVerifierHTTPFailure, ClaimVerifierInputBudgetExceeded,
    ClaimVerifierInvalidVerdicts, ClaimVerifierMalformedResponse, ClaimVerifierTruncatedResponse,
    ClaimVerifierTimeout,
)


class LocalClaimVerifierTests(unittest.TestCase):
    def run_verifier(self, verdicts):
        observed = {}

        def handler(request):
            body = json.loads(request.content)
            observed.update(body=body)
            return httpx.Response(200, json={"done_reason": "stop", "eval_count": 61,
                "prompt_eval_count": 42,
                "message": {"content": json.dumps({"verdicts": verdicts})}})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model")
        return verifier, client, observed

    def test_valid_verdict_is_bound_to_supplied_claim_and_evidence(self):
        verdicts = [{"claim_id": "C1", "status": "supported", "supporting_citations": ["S1"],
                     "contradicting_citations": []}]
        verifier, client, observed = self.run_verifier(verdicts)
        with client:
            result = verifier.verify([{"claim_id": "C1", "text": "A fact", "citation_ids": ["S1"]}],
                                     [{"citation_id": "S1", "chunk_id": "chunk-1", "text": "A fact."}])
        self.assertEqual(result.verdicts[0].status, "supported")
        self.assertEqual(result.verdicts[0].claim_text, "A fact")
        self.assertEqual(result.verdicts[0].supporting_evidence_ids, ("chunk-1",))
        self.assertEqual(result.verdicts[0].supporting_citations, ("S1",))
        self.assertIsNone(result.verdicts[0].rejection_reason)
        self.assertEqual(result.overall_verdict, "verified")
        self.assertTrue(observed["body"]["messages"][0]["content"].find("untrusted") >= 0)
        verifier_instruction = observed["body"]["messages"][0]["content"].lower()
        self.assertIn("unsupported and uncertain require both citation arrays to be empty", verifier_instruction)
        self.assertIn("supported requires at least one supporting citation", verifier_instruction)
        schema = observed["body"]["format"]
        self.assertEqual(schema["properties"]["verdicts"]["minItems"], 1)
        self.assertEqual(schema["properties"]["verdicts"]["maxItems"], 1)
        self.assertEqual(schema["properties"]["verdicts"]["items"]["properties"]["claim_id"]["enum"], ["C1"])
        self.assertEqual(schema["properties"]["verdicts"]["items"]["properties"]["supporting_citations"]["items"]["enum"], ["S1"])
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["verdicts"]["items"]["additionalProperties"])
        self.assertEqual(result.output_token_allowance, 192)
        self.assertEqual(result.done_reason, "stop")

    def test_unknown_citation_and_wrong_claim_ids_fail_closed(self):
        variants = [
            [{"claim_id": "C1", "status": "supported", "supporting_citations": ["S9"], "contradicting_citations": []}],
            [{"claim_id": "C2", "status": "supported", "supporting_citations": ["S1"], "contradicting_citations": []}],
        ]
        for verdicts in variants:
            verifier, client, _ = self.run_verifier(verdicts)
            with client, self.assertRaises(ClaimVerifierInvalidVerdicts):
                verifier.verify([{"claim_id": "C1", "text": "A", "citation_ids": ["S1"]}],
                                [{"citation_id": "S1", "text": "A"}])

    def test_unsupported_claim_retains_text_evidence_and_rejection_reason(self):
        verdicts = [{"claim_id": "C1", "status": "unsupported", "supporting_citations": [],
                     "contradicting_citations": []}]
        verifier, client, _ = self.run_verifier(verdicts)
        with client:
            result = verifier.verify([{"claim_id": "C1", "text": "Unsupported claim", "citation_ids": ["S1"]}],
                [{"citation_id": "S1", "chunk_id": "chunk-1", "text": "Different source text"}])
        row = result.verdicts[0]
        self.assertEqual(row.claim_text, "Unsupported claim")
        self.assertEqual(row.status, "unsupported")
        self.assertEqual(row.supporting_evidence_ids, ())
        self.assertEqual(row.rejection_reason, "no_entailing_evidence")
        self.assertEqual(result.overall_verdict, "rejected")

    def test_inconsistent_unsupported_citation_output_fails_closed(self):
        verdicts = [{"claim_id": "C1", "status": "unsupported", "supporting_citations": ["S1"],
                     "contradicting_citations": []}]
        verifier, client, _ = self.run_verifier(verdicts)
        with client, self.assertRaises(ClaimVerifierInvalidVerdicts) as caught:
            verifier.verify([{"claim_id": "C1", "text": "Claim", "citation_ids": ["S1"]}],
                            [{"citation_id": "S1", "chunk_id": "chunk-1", "text": "Evidence"}])
        self.assertEqual(caught.exception.failure_reason, "non_supported_verdict_has_citation")

    def test_invalid_verifier_rows_have_specific_fail_closed_reason(self):
        variants = [
            ([{"claim_id": "C1", "status": "supported", "supporting_citations": ["S9"],
               "contradicting_citations": []}], "invalid_verdict_fields_or_citation_ids"),
            ([{"claim_id": "C1", "status": "supported", "supporting_citations": [],
               "contradicting_citations": []}], "supported_verdict_has_inconsistent_citations"),
            ([{"claim_id": "C1", "status": "unsupported", "supporting_citations": ["S1"],
               "contradicting_citations": []}], "non_supported_verdict_has_citation"),
        ]
        for verdicts, reason in variants:
            verifier, client, _ = self.run_verifier(verdicts)
            with client, self.assertRaises(ClaimVerifierInvalidVerdicts) as caught:
                verifier.verify([{"claim_id": "C1", "text": "Claim", "citation_ids": ["S1"]}],
                                [{"citation_id": "S1", "chunk_id": "chunk-1", "text": "Evidence"}])
            self.assertEqual(caught.exception.failure_reason, reason)

    def test_incomplete_or_inconsistent_supported_verdict_fails_closed(self):
        for verdicts in ([], [{"claim_id": "C1", "status": "supported", "supporting_citations": [],
                              "contradicting_citations": []} ]):
            verifier, client, _ = self.run_verifier(verdicts)
            with client, self.assertRaises(ClaimVerifierInvalidVerdicts):
                verifier.verify([{"claim_id": "C1", "text": "A", "citation_ids": ["S1"]}],
                                [{"citation_id": "S1", "text": "A"}])

    def test_missing_verdicts_duplicates_unknown_ids_status_and_citation_consistency_fail(self):
        variants = [
            {},
            {"verdicts": [{"claim_id": "C1", "status": "supported", "supporting_citations": ["S1"], "contradicting_citations": []},
                          {"claim_id": "C1", "status": "supported", "supporting_citations": ["S1"], "contradicting_citations": []}]},
            {"verdicts": [{"claim_id": "C9", "status": "supported", "supporting_citations": ["S1"], "contradicting_citations": []}]},
            {"verdicts": [{"claim_id": "C1", "status": "made_up", "supporting_citations": ["S1"], "contradicting_citations": []}]},
            {"verdicts": [{"claim_id": "C1", "status": "supported", "supporting_citations": ["S9"], "contradicting_citations": []}]},
            {"verdicts": [{"claim_id": "C1", "status": "supported", "supporting_citations": [], "contradicting_citations": []}]},
            {"verdicts": [{"claim_id": "C1", "status": "contradicted", "supporting_citations": [], "contradicting_citations": []}]},
        ]
        for value in variants:
            client = httpx.Client(transport=httpx.MockTransport(lambda request, value=value:
                httpx.Response(200, json={"message": {"content": json.dumps(value)}})))
            verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model", max_retries=0)
            with client, self.assertRaises(ClaimVerifierInvalidVerdicts):
                verifier.verify([{"claim_id": "C1", "text": "A", "citation_ids": ["S1"]}],
                                [{"citation_id": "S1", "text": "A"}])

    def test_malformed_nested_json_fails_closed(self):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"message": {"content": '{"verdicts":[{'}})))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model", max_retries=0)
        with client, self.assertRaises(ClaimVerifierMalformedResponse):
            verifier.verify([{"claim_id": "C1", "text": "A"}], [{"citation_id": "S1", "text": "A"}])

    def test_timeout_and_http_failure_are_distinct_and_keep_causes(self):
        def timeout_handler(request):
            raise httpx.ReadTimeout("private evidence", request=request)
        client = httpx.Client(transport=httpx.MockTransport(timeout_handler))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model", max_retries=0)
        with client, self.assertRaises(ClaimVerifierTimeout) as caught:
            verifier.verify([{"claim_id": "C1", "text": "A"}], [{"citation_id": "S1", "text": "A"}])
        self.assertEqual(caught.exception.error_code, "claim_verifier_timeout")
        self.assertIsInstance(caught.exception.__cause__, httpx.ReadTimeout)
        self.assertNotIn("private", str(caught.exception))

        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503, text="secret")))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model", max_retries=0)
        with client, self.assertRaises(ClaimVerifierHTTPFailure) as caught_http:
            verifier.verify([{"claim_id": "C1", "text": "A"}], [{"citation_id": "S1", "text": "A"}])
        self.assertEqual(caught_http.exception.http_status, 503)
        self.assertIsInstance(caught_http.exception.__cause__, httpx.HTTPStatusError)

    def test_connection_failure_is_classified_separately(self):
        def handler(request):
            raise httpx.ConnectError("local endpoint refused", request=request)
        client = httpx.Client(transport=httpx.MockTransport(handler))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model", max_retries=0)
        with client, self.assertRaises(ClaimVerifierConnectionFailure) as caught:
            verifier.verify([{"claim_id": "C1", "text": "A"}], [{"citation_id": "S1", "text": "A"}])
        self.assertEqual(caught.exception.error_code, "claim_verifier_connection_failure")
        self.assertIsInstance(caught.exception.__cause__, httpx.ConnectError)

    def test_malformed_verifier_json_is_distinct_from_invalid_verdicts(self):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"message": {"content": "not-json"}})))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model", max_retries=0)
        with client, self.assertRaises(ClaimVerifierMalformedResponse):
            verifier.verify([{"claim_id": "C1", "text": "A"}], [{"citation_id": "S1", "text": "A"}])

    def test_verifier_input_budget_failure_is_classified_before_request(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda request: self.fail("request must not be sent")))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model",
                                      max_output_tokens=384, context_window_tokens=700)
        with client, self.assertRaises(ClaimVerifierInputBudgetExceeded):
            verifier.verify([{"claim_id": "C1", "text": "A"}],
                            [{"citation_id": "S1", "text": "x" * 1000}])

    def test_token_estimate_uses_codepoints_not_multibyte_utf8_length(self):
        text = "漢字かなカナ🙂" * 20
        estimate = conservative_qwen_token_estimate(text)
        self.assertGreater(estimate, 0)
        self.assertLess(estimate, len(text.encode("utf-8")))

    def test_verifier_input_budget_includes_system_schema_and_message_overhead(self):
        claims = [{"claim_id": "C1", "text": "A", "citation_ids": ["S1"]}]
        evidence = [{"citation_id": "S1", "chunk_id": "chunk-1", "text": "A"}]
        schema = LocalClaimVerifier._schema(["C1"], ["S1"])
        user_prompt = json.dumps({"claims": claims, "evidence": evidence}, ensure_ascii=False, separators=(",", ":"))
        schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        expected_floor = (conservative_qwen_token_estimate(VERIFIER_SYSTEM_PROMPT)
                          + conservative_qwen_token_estimate(user_prompt)
                          + conservative_qwen_token_estimate(schema_text) + 64)
        captured = {}
        def handler(request):
            captured["payload"] = json.loads(request.content)
            return httpx.Response(200, json={"done_reason": "stop", "eval_count": 60,
                "prompt_eval_count": 300, "message": {"content": json.dumps({"verdicts": [
                    {"claim_id": "C1", "status": "supported", "supporting_citations": ["S1"],
                     "contradicting_citations": []}]})}})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        output_cap, margin = 192, 64
        window = expected_floor + output_cap + margin
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model",
            max_output_tokens=output_cap, context_window_tokens=window, input_safety_margin_tokens=margin)
        with client:
            result = verifier.verify(claims, evidence)
        self.assertEqual(result.estimated_input_tokens, expected_floor)
        self.assertEqual(captured["payload"]["options"]["num_ctx"], window)
        self.assertEqual(result.eval_count, 60)
        self.assertEqual(result.prompt_eval_count, 300)

    def test_input_budget_boundary_fails_one_token_below_and_never_sends_request(self):
        claims = [{"claim_id": "C1", "text": "A", "citation_ids": ["S1"]}]
        evidence = [{"citation_id": "S1", "chunk_id": "chunk-1", "text": "A"}]
        schema = LocalClaimVerifier._schema(["C1"], ["S1"])
        prompt = json.dumps({"claims": claims, "evidence": evidence}, ensure_ascii=False, separators=(",", ":"))
        schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        estimate = (conservative_qwen_token_estimate(VERIFIER_SYSTEM_PROMPT)
            + conservative_qwen_token_estimate(prompt) + conservative_qwen_token_estimate(schema_text) + 64)
        cap, margin = 192, 32
        client = httpx.Client(transport=httpx.MockTransport(lambda request: self.fail("HTTP must not be sent")))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model",
            max_output_tokens=cap, context_window_tokens=estimate + cap + margin - 1,
            input_safety_margin_tokens=margin)
        with client, self.assertRaises(ClaimVerifierInputBudgetExceeded) as caught:
            verifier.verify(claims, evidence)
        self.assertEqual(caught.exception.verification_input_tokens_estimated, estimate)

    def test_multiple_claims_receive_bounded_output_allowance(self):
        claims = [{"claim_id": f"C{i}", "text": f"Claim {i}", "citation_ids": ["S1"]} for i in range(1, 4)]
        rows = [{"claim_id": claim["claim_id"], "status": "supported", "supporting_citations": ["S1"],
                 "contradicting_citations": []} for claim in claims]
        observed = {}
        def handler(request):
            observed["payload"] = json.loads(request.content)
            return httpx.Response(200, json={"done_reason": "stop", "eval_count": 120,
                "prompt_eval_count": 500, "message": {"content": json.dumps({"verdicts": rows})}})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model", max_output_tokens=512)
        with client:
            result = verifier.verify(claims, [{"citation_id": "S1", "chunk_id": "chunk-1", "text": "Evidence"}])
        self.assertEqual(result.output_token_allowance, 448)
        self.assertEqual(observed["payload"]["options"]["num_predict"], 448)

    def test_done_reason_length_is_reported_as_truncated_with_safe_metadata(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            "done_reason": "length", "eval_count": 192, "prompt_eval_count": 321,
            "message": {"content": '{"verdicts":[{"claim_id":"C1"}'}})))
        verifier = LocalClaimVerifier(client, "http://127.0.0.1:11434", "local-model", max_retries=0)
        with client, self.assertRaises(ClaimVerifierTruncatedResponse) as caught:
            verifier.verify([{"claim_id": "C1", "text": "private claim"}],
                            [{"citation_id": "S1", "text": "private evidence"}])
        self.assertEqual(caught.exception.verification_done_reason, "length")
        self.assertEqual(caught.exception.verification_eval_count, 192)
        self.assertEqual(caught.exception.verification_prompt_eval_count, 321)
        self.assertEqual(caught.exception.verification_response_chars, len('{"verdicts":[{"claim_id":"C1"}'))
        self.assertNotIn("private", str(caught.exception))

    def test_sanitized_diagnostics_do_not_include_prompt_evidence_or_response_text(self):
        from scripts.test_rag_generation import classify_generation_error
        error = ClaimVerifierMalformedResponse()
        error.__cause__ = json.JSONDecodeError("bad JSON containing private text", "PRIVATE_PROMPT_EVIDENCE_RESPONSE", 0)
        record = classify_generation_error(error)
        serialized = json.dumps(record)
        self.assertEqual(record["original_cause_type"], "JSONDecodeError")
        self.assertNotIn("PRIVATE_PROMPT_EVIDENCE_RESPONSE", serialized)
        self.assertNotIn("bad JSON", serialized)


if __name__ == "__main__":
    unittest.main()
