"""SQLAlchemy database models with binary file storage."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Enum, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from disparaai.models.campaign import CampaignStatus

Base = declarative_base()


class Campaign(Base):
    """Campaign database model with direct file storage."""
    __tablename__ = "campaigns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_phone = Column(String(20), nullable=False, index=True)
    name = Column(String(200))
    status = Column(Enum(CampaignStatus), default=CampaignStatus.PENDING, nullable=False)
    message_content = Column(Text)  # Final approved message content
    
    # CSV file storage (base64 from Evolution API webhook)
    csv_file_data = Column(LargeBinary)  # CSV file binary data
    csv_filename = Column(String(255))  # Original CSV filename
    csv_mime_type = Column(String(100))  # CSV MIME type
    csv_size_bytes = Column(Integer)  # CSV file size
    
    # Image file storage (base64 from Evolution API webhook)
    image_file_data = Column(LargeBinary)  # Image file binary data
    image_filename = Column(String(255))  # Original image filename
    image_mime_type = Column(String(100))  # Image MIME type
    image_size_bytes = Column(Integer)  # Image file size
    image_width = Column(Integer)  # Image width in pixels
    image_height = Column(Integer)  # Image height in pixels
    
    # Campaign metrics
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    phone_numbers = relationship("PhoneNumber", back_populates="campaign", cascade="all, delete-orphan")


class PhoneNumber(Base):
    """Phone number database model."""
    __tablename__ = "phone_numbers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    raw = Column(String(50), nullable=False)
    formatted = Column(String(20), nullable=False)
    country_code = Column(String(3))
    is_valid = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="phone_numbers")

