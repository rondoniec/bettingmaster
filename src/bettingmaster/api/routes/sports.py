from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.models.league import League
from bettingmaster.models.sport import Sport
from bettingmaster.schemas.common import LeagueOut, SportOut

router = APIRouter()


@router.get("/sports", response_model=list[SportOut])
def list_sports(db: Session = Depends(get_db)):
    return db.query(Sport).all()


@router.get("/sports/{sport_id}/leagues", response_model=list[LeagueOut])
def list_leagues(sport_id: str, db: Session = Depends(get_db)):
    return db.query(League).filter(League.sport_id == sport_id).all()


@router.get("/leagues/{league_id}", response_model=LeagueOut)
def get_league(league_id: str, db: Session = Depends(get_db)):
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league
