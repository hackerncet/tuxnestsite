"""Tests that production deployment fails safely without valid configuration."""
import pytest
from cryptography.fernet import Fernet
from app.serve import validate_configuration
from deploy.write_compose_env import compose_env_value, compose_environment


def production_env():
    return {
        'APP_ENV': 'production',
        'DATABASE_URL': 'postgresql://user:secret@db-host/internaldb',
        'PUBLIC_ORIGIN': 'https://ncet-verifyflow.onrender.com',
        'SETTINGS_ENCRYPTION_KEY': Fernet.generate_key().decode(),
    }


def test_development_does_not_require_production_secrets():
    validate_configuration({'APP_ENV': 'development'})


def test_production_valid_internal_database():
    validate_configuration(production_env())


def test_external_render_database_requires_tls():
    env = production_env()
    env['DATABASE_URL'] = 'postgresql://u:p@dpg-any.oregon-postgres.render.com/db'
    with pytest.raises(RuntimeError, match='sslmode=require'):
        validate_configuration(env)
    env['DATABASE_URL'] += '?sslmode=require'
    validate_configuration(env)


def test_production_rejects_sqlite():
    env = production_env()
    env['DATABASE_URL'] = 'sqlite:///temporary.db'
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        validate_configuration(env)


def test_production_rejects_invalid_origin():
    env = production_env()
    env['PUBLIC_ORIGIN'] = 'http://localhost:8000'
    with pytest.raises(RuntimeError, match='HTTPS'):
        validate_configuration(env)


def test_production_requires_real_encryption_key():
    env = production_env()
    env['SETTINGS_ENCRYPTION_KEY'] = 'invalid'
    with pytest.raises(RuntimeError, match='Fernet'):
        validate_configuration(env)


def test_compose_env_quotes_complex_admin_passwords_literally():
    password = "NCET!$ shell # chars 'quoted' \\ safe"
    written = compose_environment({'NCET_BOOTSTRAP_ADMIN_PASSWORD': password})
    assert written == "NCET_BOOTSTRAP_ADMIN_PASSWORD='NCET!$ shell # chars \\'quoted\\' \\\\ safe'\n"
    with pytest.raises(ValueError, match='one line'):
        compose_env_value("line\nbreak")

