

from db.repository import PropertyRepository


class PropertyService:
    def __init__(self, db_session):
        self.db_session = db_session
        self.repository = PropertyRepository(db_session)

    async def add_property(self, property_data):
        # Logic to add property using the repository
        pass

    async def get_properties(self):
        # Logic to retrieve properties using the repository
        pass
