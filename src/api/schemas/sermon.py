from src.api.schemas.content import PublicSermon as PublicSermonRecord,PublicSermonCollection,PublicImage

class PublicSermonTaxonomy(PublicSermonCollection):
    description:str
    image:PublicImage|None=None
    sermon_count:int
