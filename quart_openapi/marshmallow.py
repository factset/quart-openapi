"""marshmallow.py

Provide optional integration with marshmallow
"""
try:
    # pylint: disable=unused-import
    from marshmallow import Schema, ValidationError as MarshmallowValidationError
    from marshmallow_jsonschema import JSONSchema

    def schema_to_json(schema: Schema):
        """Convert marshmallow.Schema to valid json schema

        :param schema: the marshmallow.Schema to convert
        :return: the converted json schema
        """
        return JSONSchema().dump(schema)

    MARSHMALLOW = True
except ImportError:
    Schema = None
    JSONSchema = None
    MarshmallowValidationError = None
    MARSHMALLOW = False
