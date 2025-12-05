"""
Call Statistics Service - Calculate call statistics for admin dashboard
"""
from typing import Dict
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func, case
from sqlalchemy.sql import extract
from app.database.connection import AsyncSessionLocal
from app.models.call import Call


async def get_call_statistics(real_estate_agent_id: str, period: str = "week") -> Dict:
    """
    Get call statistics for an agent
    period: 'day' | 'week' | 'month'
    """
    if period not in ["day", "week", "month"]:
        raise ValueError("Period must be 'day', 'week', or 'month'")
    
    async with AsyncSessionLocal() as session:
        # Calculate date range
        now = datetime.utcnow()
        if period == "day":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # month
            start_date = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Base query
        base_conditions = [
            Call.real_estate_agent_id == real_estate_agent_id,
            Call.created_at >= start_date
        ]
        where_clause = and_(*base_conditions)
        
        # Total calls
        total_stmt = select(func.count()).select_from(Call).where(where_clause)
        total_result = await session.execute(total_stmt)
        total_calls = total_result.scalar_one() or 0
        
        # Completed calls
        completed_stmt = select(func.count()).select_from(Call).where(
            and_(where_clause, Call.status == "completed")
        )
        completed_result = await session.execute(completed_stmt)
        completed_calls = completed_result.scalar_one() or 0
        
        # Failed calls
        failed_statuses = ["failed", "busy", "no-answer"]
        failed_stmt = select(func.count()).select_from(Call).where(
            and_(where_clause, Call.status.in_(failed_statuses))
        )
        failed_result = await session.execute(failed_stmt)
        failed_calls = failed_result.scalar_one() or 0
        
        # Total duration
        duration_stmt = select(func.sum(Call.duration_seconds)).where(where_clause)
        duration_result = await session.execute(duration_stmt)
        total_duration = duration_result.scalar_one() or 0
        total_duration = int(total_duration) if total_duration else 0
        
        # Average duration
        avg_duration = total_duration / completed_calls if completed_calls > 0 else 0
        
        # Calls by status
        status_stmt = (
            select(Call.status, func.count(Call.id).label("count"))
            .where(where_clause)
            .group_by(Call.status)
        )
        status_result = await session.execute(status_stmt)
        calls_by_status = {row.status: row.count for row in status_result}
        
        # Calls by day (for chart)
        calls_by_day = []
        if period == "day":
            # Group by hour
            hour_stmt = (
                select(
                    extract("hour", Call.created_at).label("hour"),
                    func.count(Call.id).label("count")
                )
                .where(where_clause)
                .group_by(extract("hour", Call.created_at))
                .order_by(extract("hour", Call.created_at))
            )
            hour_result = await session.execute(hour_stmt)
            for row in hour_result:
                calls_by_day.append({
                    "date": f"{now.strftime('%Y-%m-%d')} {int(row.hour):02d}:00",
                    "count": row.count
                })
        else:
            # Group by day
            day_stmt = (
                select(
                    func.date(Call.created_at).label("date"),
                    func.count(Call.id).label("count")
                )
                .where(where_clause)
                .group_by(func.date(Call.created_at))
                .order_by(func.date(Call.created_at))
            )
            day_result = await session.execute(day_stmt)
            for row in day_result:
                calls_by_day.append({
                    "date": row.date.strftime("%Y-%m-%d") if hasattr(row.date, 'strftime') else str(row.date),
                    "count": row.count
                })
        
        return {
            "period": period,
            "total_calls": total_calls,
            "completed_calls": completed_calls,
            "failed_calls": failed_calls,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": round(avg_duration, 2),
            "calls_by_status": calls_by_status,
            "calls_by_day": calls_by_day
        }

