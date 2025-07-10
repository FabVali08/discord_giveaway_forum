from pydantic_settings import BaseSettings
from typing import ClassVar
import os
from dotenv import load_dotenv

load_dotenv(".env")

class Settings(BaseSettings):
    TOKEN: str = os.getenv("TOKEN")
    
settings = Settings()