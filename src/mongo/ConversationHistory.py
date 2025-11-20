from pydantic import BaseModel, Field
from mongo.schema import line_user_id_field
from anthropic.types.beta import BetaMessageParam
from typing import List
from datetime import datetime

class ConversationHistoryModel(BaseModel):
    line_user_id: str = line_user_id_field
    history: List[BetaMessageParam] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)