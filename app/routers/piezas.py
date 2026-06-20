from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.auth import get_current_user
from app.models.usuario import Usuario

router = APIRouter()
