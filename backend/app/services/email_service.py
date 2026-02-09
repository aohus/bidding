import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from jinja2 import Environment, FileSystemLoader


class EmailService:
    """Service for sending emails using SMTP"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.from_name = settings.FROM_NAME
        
        # Setup Jinja2 template environment
        template_dir = Path(__file__).parent.parent / "templates" / "email"
        self.template_env = Environment(loader=FileSystemLoader(str(template_dir)))
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email using SMTP
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text content (optional)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Add plain text part
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
            
            return True
            
        except Exception as e:
            print(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    async def send_bid_notification(
        self,
        to_email: str,
        username: str,
        bid_notices: List[dict]
    ) -> bool:
        """
        Send bid notification email to user
        
        Args:
            to_email: User's email address
            username: User's username
            bid_notices: List of bid notices matching user's preferences
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Render HTML template
            template = self.template_env.get_template("bid_notification.html")
            html_content = template.render(
                username=username,
                bid_notices=bid_notices,
                total_count=len(bid_notices)
            )
            
            # Render text template
            text_template = self.template_env.get_template("bid_notification.txt")
            text_content = text_template.render(
                username=username,
                bid_notices=bid_notices,
                total_count=len(bid_notices)
            )
            
            subject = f"새로운 입찰 공고 {len(bid_notices)}건이 등록되었습니다"
            
            return await self.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            print(f"Failed to send bid notification: {str(e)}")
            return False
    
    async def send_welcome_email(
        self,
        to_email: str,
        username: str
    ) -> bool:
        """
        Send welcome email to new user
        
        Args:
            to_email: User's email address
            username: User's username
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            template = self.template_env.get_template("welcome.html")
            html_content = template.render(username=username)
            
            text_template = self.template_env.get_template("welcome.txt")
            text_content = text_template.render(username=username)
            
            subject = "입찰 정보 시스템에 오신 것을 환영합니다"
            
            return await self.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            print(f"Failed to send welcome email: {str(e)}")
            return False


# Singleton instance
email_service = EmailService()