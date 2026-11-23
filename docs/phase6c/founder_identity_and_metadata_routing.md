# Founder identity and trusted metadata routing

## Configured fields

The `CreatorProfile` record seeded by `accounts.0002_seed_creator_profile` contains the verified name **Ishan Kaushik** and these exact owner-supplied profile URLs:

- LinkedIn: `https://www.linkedin.com/in/ishankaushik/`
- GitHub: `https://github.com/Ishan10123`
- LeetCode: `https://leetcode.com/u/Ishan_2003/`
- HackerRank: `https://www.hackerrank.com/profile/ishurbt1`
- Portfolio: `https://portfolio-three-mauve-72.vercel.app/`

Instagram is unset. No employment, education, qualification, skill, biography, or additional project facts were seeded because the latest verified input did not establish those details. No phone number was present in the request, and no phone value was stored.

## Routing

`accounts.founder_metadata.answer_creator_question()` recognizes founder/creator/project-owner intents and reads the single trusted profile. `chat.views.message_create()` checks this local application metadata before `get_rag_client()`. A matched question is persisted with `retrieval_mode=trusted_metadata`, `verification_status=trusted_metadata`, zero document citations, and a bounded `retrieval_performed=false` diagnostic. The chat page labels the answer as public creator-profile metadata, separate from documentation retrieval.

Only enabled public fields are returned. If the public profile is disabled, the answer says verified creator details are not enabled. Tests patch the RAG client and assert it is never called. Ordinary documentation questions continue through the configured RAG adapter unchanged.
