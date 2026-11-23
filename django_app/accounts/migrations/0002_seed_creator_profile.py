from django.db import migrations


def seed_creator_profile(apps, schema_editor):
    CreatorProfile = apps.get_model("accounts", "CreatorProfile")
    CreatorProfile.objects.using(schema_editor.connection.alias).update_or_create(
        key="satell",
        defaults={
            "full_name": "Ishan Kaushik",
            "linkedin_url": "https://www.linkedin.com/in/ishankaushik/",
            "github_url": "https://github.com/Ishan10123",
            "leetcode_url": "https://leetcode.com/u/Ishan_2003/",
            "hackerrank_url": "https://www.hackerrank.com/profile/ishurbt1",
            "portfolio_url": "https://portfolio-three-mauve-72.vercel.app/",
            "profile_is_public": True,
            "name_is_public": True,
            "linkedin_is_public": True,
            "github_is_public": True,
            "leetcode_is_public": True,
            "hackerrank_is_public": True,
            "portfolio_is_public": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed_creator_profile, migrations.RunPython.noop)]
