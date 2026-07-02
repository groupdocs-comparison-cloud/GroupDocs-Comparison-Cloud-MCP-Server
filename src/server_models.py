from pydantic import BaseModel, Field


class StorageFile(BaseModel):
    name: str = Field(description="File name")
    is_folder: bool = Field(description="Is it a folder")
    size: int = Field(description="File size in bytes")
    modified_date: str | None = Field(default=None, description="Last modified date")


class DownloadedFile(BaseModel):
    path: str = Field(description="Cloud path requested")
    name: str = Field(description="File name")
    base64_data: str = Field(description="File content encoded as base64")
    size: int = Field(description="Size in bytes")


class SupportedFileFormat(BaseModel):
    file_format: str | None = Field(default=None, description="Format name")
    extension: str | None = Field(default=None, description="Primary extension")
