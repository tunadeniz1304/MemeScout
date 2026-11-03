def test_users_access_requires_auth(client):
    response = client.get("/api/v1/users")
    assert response.status_code == 401  # Giriş yapılmadan erişim engellendi

def test_admin_only_create_user(client):
    response = client.post("/api/v1/users", json={
        "kullanici_adi": "newuser",
        "gorunen_ad": "New User",
        "takma_ad": "new_user",
        "sifre": "NewPass1234",
        "admin": False
    })
    assert response.status_code == 401  # Giriş yapılmadan kullanıcı oluşturulamaz

