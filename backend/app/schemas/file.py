from pydantic import BaseModel, Field


class UploadInitIn(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    size: int = Field(ge=1, description="전체 바이트 크기")
    mime_type: str = Field(default="application/octet-stream", max_length=128)


class UploadInitOut(BaseModel):
    file_id: int
    chunk_size: int
    expected_chunks: int


class UploadCompleteOut(BaseModel):
    file_id: int
    status: str
