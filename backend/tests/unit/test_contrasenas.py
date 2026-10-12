from app.core.contrasenas import generar_contrasena_temporal, hashear, verificar


def test_el_hash_es_argon2id_y_no_contiene_la_contrasena():
    hash_guardado = hashear("una-clave-larga")

    assert hash_guardado.startswith("$argon2id$")
    assert "una-clave-larga" not in hash_guardado


def test_dos_hashes_de_la_misma_contrasena_son_distintos():
    assert hashear("una-clave-larga") != hashear("una-clave-larga")


def test_verifica_la_contrasena_correcta():
    assert verificar(hashear("una-clave-larga"), "una-clave-larga") is True


def test_rechaza_una_contrasena_incorrecta():
    assert verificar(hashear("una-clave-larga"), "otra-clave-larga") is False


def test_un_hash_que_no_es_argon2_no_verifica():
    assert verificar("no-es-un-hash", "una-clave-larga") is False


def test_la_contrasena_temporal_tiene_16_caracteres_y_cambia_cada_vez():
    primera = generar_contrasena_temporal()
    segunda = generar_contrasena_temporal()

    assert len(primera) == len(segunda) == 16
    assert primera != segunda


def test_la_contrasena_temporal_se_puede_copiar_y_escribir_sin_ambiguedades():
    """Solo letras y dígitos, sin los que se confunden al leerlos (0/O, 1/l/I)."""
    generadas = "".join(generar_contrasena_temporal() for _ in range(50))

    assert generadas.isascii() and generadas.isalnum()
    assert not set(generadas) & set("0O1lI")
