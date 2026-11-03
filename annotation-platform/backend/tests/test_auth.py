def test_register_closed_by_default(client, monkeypatch):
    monkeypatch.delenv("REGISTRATION_OPEN", raising=False)
    response = client.post("/api/v1/auth/register", json={
        "kullanici_adi": "kapaliuye",
        "sifre": "KapaliSifre123"
    })
    assert response.status_code == 403
    assert response.json()["hata"]["kod"] == "KAYIT_KAPALI"


def test_register_login_flow(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_OPEN", "1")
    username = "testuser"
    password = "TestPass1234"

    # Kayıt testi
    response = client.post("/api/v1/auth/register", json={
        "kullanici_adi": username,
        "sifre": password
    })
    assert response.status_code == 201
    data = response.json()
    assert "erisim_token" in data
    assert data["kullanici"]["kullanici_adi"] == username

    # Yinelenen kayda izin verilmemeli
    response = client.post("/api/v1/auth/register", json={
        "kullanici_adi": username,
        "sifre": password
    })
    assert response.status_code == 409

    # Giriş testi
    response = client.post("/api/v1/auth/login", json={
        "kullanici_adi": username,
        "sifre": password
    })
    assert response.status_code == 200
    data = response.json()
    assert "erisim_token" in data

    # Hatalı giriş
    response = client.post("/api/v1/auth/login", json={
        "kullanici_adi": username,
        "sifre": "yanlis1234"
    })
    assert response.status_code == 401

    # Me endpoint kontrolü
    token = data["erisim_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["kullanici_adi"] == username
