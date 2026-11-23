# Chat experience refinement

Existing first-message title generation and manual-title override were inspected and retained in `chat.views.message_create()` and `conversations.title_utils.title_from_first_question()`. Empty conversations retain “New conversation”; first meaningful input creates a title unless a manual title exists. Existing rename, exports, share expiry/revocation, lock/unlock, deletion, and ownership-filtered queries were not replaced.

The chat continues to align user messages right and Satell messages left. The generic partial-evidence footer was already absent; partially verified answers retain their status badge without a confusing technical footer. Trusted creator answers have no document citations and a distinct metadata-origin note. Ordinary RAG citations remain attached to persisted messages and can optionally be hidden by the user's source-card display preference without changing validation.

No normal RAG query was counted as a live result in this phase. Django/PostgreSQL-to-FastAPI/Ollama end-to-end revalidation awaits Docker service availability; previous phase evidence remains historical and was not repeated here.
