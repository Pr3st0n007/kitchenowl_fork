from app.helpers.encryption import decrypt_secret, encrypt_secret, reset_for_tests


def test_round_trip():
    reset_for_tests()
    cipher = encrypt_secret("hello-world")
    assert cipher != "hello-world"
    assert decrypt_secret(cipher) == "hello-world"


def test_distinct_ciphertexts_for_same_plaintext():
    reset_for_tests()
    a = encrypt_secret("same")
    b = encrypt_secret("same")
    # Fernet uses a random IV, so ciphertexts must differ.
    assert a != b
    assert decrypt_secret(a) == "same"
    assert decrypt_secret(b) == "same"
