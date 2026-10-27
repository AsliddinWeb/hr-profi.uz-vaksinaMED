from app.rbac import covers, matches
from app.security import generate_temp_password, validate_password_strength
from app.services.logins import base_login, slugify


def test_matches_exact_wildcard_and_star():
    assert matches({"users.read"}, "users.read")
    assert not matches({"users.read"}, "users.create")
    assert matches({"users.*"}, "users.create")
    assert not matches({"users.*"}, "roles.read")
    assert matches({"*"}, "anything.at.all")
    assert matches({"a.*"}, "a.b.c")


def test_covers_prevents_escalation():
    assert covers({"*"}, {"users.*", "roles.manage", "*"})
    assert covers({"users.*"}, {"users.read", "users.create"})
    assert covers({"users.*"}, {"users.*"})
    assert not covers({"users.read"}, {"users.*"})
    assert not covers({"users.read"}, {"users.read", "audit.read"})
    assert not covers({"users.*"}, {"*"})
    assert covers(set(), set())


def test_password_strength():
    assert validate_password_strength("short1", "x") == "password_too_short"
    assert validate_password_strength("abcdefghij", "x") == "password_too_simple"
    assert validate_password_strength("1234567890", "x") == "password_too_simple"
    assert validate_password_strength("ali.valiyev1", "ali.valiyev1") == "password_same_as_login"
    assert validate_password_strength("Good-pass1", "ali") is None


def test_temp_password_has_letter_and_digit_and_no_confusing_chars():
    for _ in range(50):
        p = generate_temp_password()
        assert len(p) == 10
        assert any(c.isdigit() for c in p) and any(c.isalpha() for c in p)
        assert not set(p) & set("0O1lI")


def test_slugify_and_logins():
    assert slugify("O'g'li") == "ogli"
    assert base_login("Tursunboyev Orifjon") == "tursunboyev.orifjon"
    assert base_login("Собиров Асадбек") == "sobirov.asadbek"
    assert base_login("Қодиров Ғайрат Ўткирович") == "qodirov.gayrat"
    assert base_login("   ") == "user"
