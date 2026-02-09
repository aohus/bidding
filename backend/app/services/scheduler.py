import asyncio
from datetime import datetime, timedelta
from typing import List

from app.db.database import AsyncSessionLocal
from app.models.user import User, UserPreference
from app.schemas.bid import BidSearchParams
from app.services.email_service import email_service
from app.services.narajangter import narajangter_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class NotificationScheduler:
    """Background task scheduler for checking new bid notices and sending notifications"""
    
    def __init__(self):
        self.is_running = False
        self.check_interval = 3600  # Check every hour
    
    async def start(self):
        """Start the scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        print("Notification scheduler started")
        
        while self.is_running:
            try:
                await self.check_and_notify()
            except Exception as e:
                print(f"Error in notification scheduler: {str(e)}")
            
            # Wait for next check
            await asyncio.sleep(self.check_interval)
    
    async def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        print("Notification scheduler stopped")
    
    async def check_and_notify(self):
        """Check for new bid notices and send notifications to users"""
        print(f"Checking for new bid notices at {datetime.now()}")
        
        async with AsyncSessionLocal() as db:
            # Get all users with email notifications enabled
            result = await db.execute(
                select(User, UserPreference)
                .join(UserPreference, User.user_id == UserPreference.user_id)
                .where(UserPreference.email_notifications_enabled == True)
            )
            users_with_prefs = result.all()
            
            for user, preference in users_with_prefs:
                try:
                    await self.notify_user(user, preference)
                except Exception as e:
                    print(f"Failed to notify user {user.username}: {str(e)}")
    
    async def notify_user(self, user: User, preference: UserPreference):
        """
        Check for new bid notices matching user's preferences and send notification
        
        Args:
            user: User object
            preference: User's preference object
        """
        if not preference.search_conditions:
            return
        
        conditions = preference.search_conditions
        
        # Get notification frequency
        frequency = preference.notification_frequency or 'daily'
        
        # Check if it's time to send notification based on frequency
        if not self._should_notify(preference, frequency):
            return
        
        # Build search parameters from user's saved conditions
        now = datetime.now()
        
        # For daily notifications, check bids from last 24 hours
        if frequency == 'daily':
            start_date = now - timedelta(days=1)
        elif frequency == 'weekly':
            start_date = now - timedelta(days=7)
        else:  # realtime
            start_date = now - timedelta(hours=1)
        
        search_params = BidSearchParams(
            inqryDiv=conditions.get('inqryDiv', '1'),
            inqryBgnDt=start_date.strftime('%Y%m%d0000'),
            inqryEndDt=now.strftime('%Y%m%d2359'),
            prtcptLmtRgnCd=conditions.get('region'),
            presmptPrceBgn=conditions.get('presmptPrceBgn'),
            presmptPrceEnd=conditions.get('presmptPrceEnd'),
            numOfRows=100,
            pageNo=1
        )
        
        # Search for bid notices
        try:
            response = await narajangter_service.search_bids(search_params)
            items = response.items
            
            if items:
                # Send email notification
                await email_service.send_bid_notification(
                    to_email=user.email,
                    username=user.username,
                    bid_notices=items
                )
                
                print(f"Sent notification to {user.username}: {len(items)} new bids")
                
        except Exception as e:
            print(f"Failed to search bids for user {user.username}: {str(e)}")
    
    def _should_notify(self, preference: UserPreference, frequency: str) -> bool:
        """
        Check if notification should be sent based on frequency and last notification time
        
        Args:
            preference: User's preference object
            frequency: Notification frequency (realtime/daily/weekly)
            
        Returns:
            bool: True if notification should be sent
        """
        if not preference.last_notification_at:
            return True
        
        now = datetime.now()
        time_since_last = now - preference.last_notification_at
        
        if frequency == 'realtime':
            return time_since_last >= timedelta(hours=1)
        elif frequency == 'daily':
            return time_since_last >= timedelta(days=1)
        elif frequency == 'weekly':
            return time_since_last >= timedelta(weeks=1)
        
        return False


# Singleton instance
notification_scheduler = NotificationScheduler()