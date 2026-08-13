from django.apps import AppConfig


class DurockConfig(AppConfig):
    """Configuration for the DuRock RJ fork app.

    Everything this fork adds lives here: data seeds and, later, its own
    models. Upstream will never create a ``durock`` app, so migrations in
    this family never collide with a release — which is the whole point.
    Schema changes to upstream models are the one thing that cannot live
    here; those stay in the app that owns the model.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "durock"
