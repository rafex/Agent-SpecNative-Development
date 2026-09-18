from specnative_pilot.intent import parse_template_command


def test_only_explicit_template_command_is_parsed():
    assert parse_template_command("/template feature-rest-endpoint").name == "feature-rest-endpoint"
    assert parse_template_command("  /template  ").name is None
    assert parse_template_command("usa una plantilla feature-rest-endpoint") is None
    assert parse_template_command("idea: /template feature-rest-endpoint") is None
