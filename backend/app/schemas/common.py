"""Small types shared by several schemas."""

from typing import Annotated

from pydantic import PlainSerializer

# Database ids are integers. In JSON they are sent as strings (the frontend treats ids as strings),
# while Python code keeps working with ints. Paths such as /businesses/42 accept the integer form.
EntityId = Annotated[int, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")]
