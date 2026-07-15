import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
RUNTIME_FILES = [
    *ROOT.glob("*.py"),
    *ROOT.joinpath("desktop").glob("*.py"),
]
FORBIDDEN_IMPORTS = {
    "requests", "httpx", "aiohttp", "socket", "smtplib", "ftplib",
    "urllib.request", "http.client",
}


def test_packaged_runtime_has_no_network_modules():
    violations = []
    for path in RUNTIME_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name in FORBIDDEN_IMPORTS:
                    violations.append(f"{path.name}: {name}")
    assert not violations, violations


def test_outlook_runtime_displays_draft_and_never_sends():
    source = (ROOT / "outlook_sender.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    send_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.lower() == "send"
    ]
    assert "mail.Display(False)" in source
    assert not send_calls


def test_repository_rules_do_not_publish_private_real_name():
    rules = (ROOT / "LOCAL_RULES.md").read_text(encoding="utf-8")
    private_name = "".join(chr(codepoint) for codepoint in (29579, 33831, 38125))

    assert private_name not in rules
