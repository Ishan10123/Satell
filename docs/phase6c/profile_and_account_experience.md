# Profile and account experience

Authenticated users have `/accounts/profile/`, `/accounts/personalization/`, and `/accounts/settings/`. A shared account dropdown exposes Profile, Personalization, Settings, About Satell, and Sign out; it shows the signed-in account's display name and email and has no upgrade/payment entry. Account profile edits only update that user's own `UserPreferences` row. Email is read-only here to avoid changing the recovery destination without a verification workflow. Password changes use Django's built-in authenticated `PasswordChangeView`.

The public `/creator/` page renders only the site creator's public fields. Public URLs are escaped and open with `target="_blank"` plus `rel="noopener noreferrer"`; only HTTPS links with the expected verified platform host are rendered. Authenticated profile editing never accepts arbitrary URLs. The creator visibility endpoint queries the profile by both its site key and `owner=request.user`; a changed URL or another user's session cannot edit it.

The creator profile owner is intentionally **unassigned** until an operator runs `python manage.py assign_creator_profile_owner --username <verified-owner-account>`. This prevents assigning controls to an assumed account. A private phone field is not present because no phone digits were supplied in the request; no phone was stored or rendered.
