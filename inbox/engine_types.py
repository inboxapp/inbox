from inbox.config import get_db_info

if get_db_info()['engine'] == 'mysql':
    from inbox.sqlalchemy_ext.util import BigJSON, BLOB, Base36UID

    BIGJSON_TYPE = BigJSON
    BLOB_TYPE = BLOB
    BASE36_TYPE = Base36UID

    ASCII_TYPE_PARAMS = dict(collation='ascii_general_ci')

else:
    from sqlalchemy.dialects.postgresql import JSON, BYTEA

    BIGJSON_TYPE = JSON
    BLOB_TYPE = BYTEA
    BASE36_TYPE = BYTEA

    ASCII_TYPE_PARAMS = {}
