"""Inspect queued uploads; stop all API/processing instances before recovering interrupted jobs."""
import argparse
from sqlalchemy import select
from src.models.sermon import SermonMediaAsset
from src.services.content_base import now
from src.services.sermon_processing import SermonProcessingService
from src.services.sermon_storage import MediaStorageService


def process_pending(factory, storage, recover_interrupted=False):
    statuses=['QUEUED','FAILED']+(['UPLOADED','PROCESSING'] if recover_interrupted else [])
    with factory() as db:
        assets=db.scalars(select(SermonMediaAsset).where(SermonMediaAsset.processing_status.in_(statuses),SermonMediaAsset.storage_provider==storage.settings.provider).order_by(SermonMediaAsset.created_at).limit(100).with_for_update(skip_locked=True)).all()
        ids=[]
        for asset in assets:
            if asset.processing_status in {'UPLOADED','PROCESSING'}:
                asset.processing_status='FAILED';asset.error_summary='Inspection was interrupted. Retry the staged upload or replace the file.';asset.updated_at=now()
            if storage.staging_path(asset.id).is_file():ids.append(asset.id)
        db.commit()
    for asset_id in ids:SermonProcessingService.process(factory,storage,asset_id)
    return len(ids)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recover-interrupted',action='store_true',help='Use only with all API/inspection processes stopped; recover interrupted staging files.')
    arguments=parser.parse_args()
    from src.config.database import SessionLocal
    print('Sermon media jobs inspected:',process_pending(SessionLocal,MediaStorageService(),arguments.recover_interrupted))
