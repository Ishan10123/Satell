from django.db import migrations, models


SEED = {
    "headline": "AI Engineer · Software Engineer · Data Scientist · Automation Engineer",
    "education": "B.Tech in Electrical Engineering, Rajasthan Technical University.\n"
                 "M.Tech in Computer Science and Engineering, Data Science and Artificial Intelligence, IIIT Kota (currently pursuing).",
    "current_role": "Software Engineer at vTech Solution Inc.",
    "experience": "Previous experience involving Python backend development, REST APIs, LLM integration, "
                  "workflow automation, RAG, and application development.",
    "skills": "Python; Machine Learning; Generative AI; LLMs; RAG; FastAPI; Django; Hugging Face; SQL; "
              "Data Engineering; Cloud Technologies; Docker; Automation; System Design.",
    "projects": "Satell — Secure RAG Chat Workspace\nAI Resume Harvesting\nFastAPI Resume Formatter\nProposal Bot",
}


def seed_owner_supplied_details(apps, schema_editor):
    CreatorProfile = apps.get_model("accounts", "CreatorProfile")
    profile = CreatorProfile.objects.using(schema_editor.connection.alias).filter(key="satell").first()
    if profile is None:
        return
    changed = []
    for field, value in SEED.items():
        if not getattr(profile, field):
            setattr(profile, field, value)
            changed.append(field)
    if changed:
        profile.verification_status = "owner_supplied_unverified"
        changed.append("verification_status")
        profile.save(using=schema_editor.connection.alias, update_fields=changed + ["updated_at"])


def reverse_seed(apps, schema_editor):
    CreatorProfile = apps.get_model("accounts", "CreatorProfile")
    profile = CreatorProfile.objects.using(schema_editor.connection.alias).filter(key="satell").first()
    if profile is None:
        return
    changed = []
    for field, value in SEED.items():
        if getattr(profile, field) == value:
            setattr(profile, field, "")
            changed.append(field)
    if profile.verification_status == "owner_supplied_unverified":
        profile.verification_status = "owner_supplied_unverified"
        changed.append("verification_status")
    if changed:
        profile.save(using=schema_editor.connection.alias, update_fields=changed + ["updated_at"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_seed_creator_profile")]

    operations = [
        migrations.AddField(
            model_name="creatorprofile", name="education",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="creatorprofile", name="current_role",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="creatorprofile", name="experience",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="creatorprofile", name="skills",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="creatorprofile", name="projects",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="creatorprofile", name="verification_status",
            field=models.CharField(
                choices=[
                    ("owner_supplied_unverified", "Supplied by owner; not independently verified"),
                    ("owner_confirmed", "Confirmed by owner"),
                    ("independently_reviewed", "Independently reviewed"),
                ], default="owner_supplied_unverified", max_length=32,
            ),
        ),
        migrations.AddField(model_name="creatorprofile", name="education_is_public",
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="creatorprofile", name="current_role_is_public",
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="creatorprofile", name="experience_is_public",
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="creatorprofile", name="skills_is_public",
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="creatorprofile", name="projects_is_public",
                            field=models.BooleanField(default=False)),
        migrations.RunPython(seed_owner_supplied_details, reverse_seed),
    ]
