from pathlib import Path
from unittest.mock import Mock,patch
import pytest
from src.services.sermon_storage import MediaStorageService,SermonStorageSettings

KEY='sermons/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222.mp4'
def test_s3_delivery_is_short_lived_and_uses_private_objects():
    settings=SermonStorageSettings(provider='S3',bucket='synthetic-private-bucket',access_key='synthetic-access',secret_key='synthetic-secret',signed_seconds=120)
    storage=MediaStorageService(settings);client=Mock();client.generate_presigned_url.return_value='https://storage.example.invalid/signed'
    with patch.object(storage,'client',return_value=client):
        url=storage.generate_signed_url(KEY,'video/mp4','HOPFAN-message.mp4','attachment')
    assert url=='https://storage.example.invalid/signed'
    params=client.generate_presigned_url.call_args.kwargs
    assert params['ExpiresIn']==120 and params['Params']['ResponseContentDisposition']=='attachment; filename="HOPFAN-message.mp4"'
    assert storage.get_public_url(KEY) is None and 'synthetic-secret' not in repr(settings)

@pytest.mark.parametrize('key',['../../.env','sermons/../../../users','C:\\Users\\Admin\\secret.mp4',KEY+'/../file','https://untrusted.invalid/file'])
def test_storage_never_accepts_arbitrary_paths(key):
    with pytest.raises(Exception):MediaStorageService().local_path(key)
