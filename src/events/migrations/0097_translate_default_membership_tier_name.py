# DuRock RJ customization: the default membership tier auto-created for every
# new organization (events/signals.py) was named "General membership" in
# English. That's now "Associação geral" going forward — this migration
# renames existing tiers still bearing the untranslated default name so
# organizations created before the signal fix aren't stuck with it.
#
# Skips (with a log warning) any organization that already has a tier
# literally named "Associação geral" — renaming there would violate the
# (organization, name) uniqueness constraint.

import typing as t

from django.db import migrations

OLD_NAME = "General membership"
NEW_NAME = "Associação geral"


def rename_default_tier(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    MembershipTier = apps.get_model("events", "MembershipTier")

    for tier in MembershipTier.objects.filter(name=OLD_NAME):
        if MembershipTier.objects.filter(organization_id=tier.organization_id, name=NEW_NAME).exists():
            continue
        tier.name = NEW_NAME
        tier.save(update_fields=["name"])


def rename_back(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    MembershipTier = apps.get_model("events", "MembershipTier")

    for tier in MembershipTier.objects.filter(name=NEW_NAME):
        if MembershipTier.objects.filter(organization_id=tier.organization_id, name=OLD_NAME).exists():
            continue
        tier.name = OLD_NAME
        tier.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0096_remove_event_public_pronoun_distribution_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_default_tier, reverse_code=rename_back),
    ]
