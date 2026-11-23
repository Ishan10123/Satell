"""Structured, payload-safe generation and verifier failures."""


class GenerationError(RuntimeError):
    error_code = "generation_error"
    error_stage = "generation"
    safe_message = "Local generation failed."

    def __init__(self, message: str | None = None, *, retry_count: int = 0,
                 http_status: int | None = None, stage: str | None = None,
                 elapsed_ms: float | None = None) -> None:
        super().__init__(message or self.safe_message)
        self.retry_count = retry_count
        self.http_status = http_status
        self.elapsed_ms = elapsed_ms
        self.answer_generation_ms = None
        self.claim_verification_ms = None
        self.generation_retry_count = 0
        self.verification_retry_count = 0
        self.generation_http_status = None
        self.verification_http_status = None
        self.total_generation_ms = None
        self.verification_done_reason = None
        self.verification_eval_count = None
        self.verification_prompt_eval_count = None
        self.verification_response_chars = None
        self.verification_output_tokens = None
        self.verification_input_tokens_estimated = None
        self.verification_context_window_tokens = None
        self.verification_safety_margin_tokens = None
        self.claim_count = None
        # These fields are consumed only by the opt-in local evaluation artifact.
        # They are never included in exception messages or ordinary API responses.
        self.failure_reason = None
        self.raw_generated_answer = None
        self.parsed_claims = ()
        self.parsed_citation_ids = ()
        self.allowed_citation_ids = ()
        self.citation_mapping = ()
        self.claim_verification = None
        self.consistency_findings = ()
        if stage is not None:
            self.error_stage = stage


class OllamaConnectionFailure(GenerationError):
    error_code = "ollama_connection_failure"
    safe_message = "Could not connect to the local Ollama service."


class OllamaTimeoutFailure(GenerationError):
    error_code = "ollama_timeout"
    safe_message = "The local Ollama request timed out."


class OllamaHTTPFailure(GenerationError):
    error_code = "ollama_http_error"
    safe_message = "The local Ollama service returned an HTTP error."


class InvalidOllamaResponse(GenerationError):
    error_code = "invalid_ollama_response"
    safe_message = "The local Ollama service returned an invalid response."


class EmptyModelResponse(GenerationError):
    error_code = "empty_model_response"
    safe_message = "The local model returned no answer text."


class CitationValidationError(GenerationError):
    error_code = "citation_validation_failed"
    error_stage = "answer_validation"
    safe_message = "Answer citations are missing or refer to unavailable sources."


class UncitedClaimError(GenerationError):
    error_code = "uncited_claim_rejected"
    error_stage = "answer_validation"
    safe_message = "Answer contains a substantive sentence without a citation."


class ClaimConsistencyError(GenerationError):
    error_code = "claim_consistency_rejected"
    error_stage = "claim_consistency"
    safe_message = "The generated claims are inconsistent or lack required version context."


class ClaimVerifierError(GenerationError):
    error_stage = "claim_verification"
    error_code = "claim_verifier_error"
    safe_message = "Local claim verification failed."


class ClaimVerifierTimeout(ClaimVerifierError):
    error_code = "claim_verifier_timeout"
    safe_message = "The local claim-verification request timed out."


class ClaimVerifierConnectionFailure(ClaimVerifierError):
    error_code = "claim_verifier_connection_failure"
    safe_message = "Could not connect to the local claim-verification service."


class ClaimVerifierHTTPFailure(ClaimVerifierError):
    error_code = "claim_verifier_http_failure"
    safe_message = "The local claim-verification service returned an HTTP error."


class ClaimVerifierMalformedResponse(ClaimVerifierError):
    error_code = "claim_verifier_malformed_response"
    safe_message = "The local claim-verification service returned a malformed response."


class ClaimVerifierTruncatedResponse(ClaimVerifierError):
    error_code = "claim_verifier_truncated_response"
    safe_message = "The local claim-verification response reached its output-token limit."


class ClaimVerifierInvalidVerdicts(ClaimVerifierError):
    error_code = "claim_verifier_invalid_verdict_set"
    safe_message = "The local claim verifier returned an incomplete or invalid verdict set."


class ClaimVerifierInputBudgetExceeded(ClaimVerifierError):
    error_code = "claim_verifier_input_budget_exceeded"
    safe_message = "Claim-verification input exceeds the configured model context budget."
