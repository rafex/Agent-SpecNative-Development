from specnative_pilot.templates import spec_template_names


def test_template_catalog_only_returns_spec_templates():
    text = """── Spec templates ─────────
     feature-rest-endpoint          Nueva ruta
       tags: rest
── Decision snippets ─────────
     jwt-authentication             JWT
"""
    assert spec_template_names(text) == {"feature-rest-endpoint"}
