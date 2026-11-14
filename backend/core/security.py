from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import uuid
import random
import string
import secrets

from db.models import User, Tenant, UserRole
from core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Custom Exceptions
class AuthError(Exception):
    """Base class for Authentication related errors"""
    pass

class DatabaseError(AuthError):
    """Raised when database operations fail"""
    pass

class AuthService:
    """Authentication Service for handling user authentication, registration, and related operations."""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password."""
        import logging
        logger = logging.getLogger(__name__)

        # Bcrypt has a 72-byte limit. Truncate if necessary before verification.
        if len(plain_password.encode('utf-8')) > 72:
            logger.warning(f"Password for verification exceeds 72 bytes ({len(plain_password.encode('utf-8'))} bytes). Truncating.")
            # Truncate to 72 bytes safely
            password_bytes = plain_password.encode('utf-8')[:72]
            plain_password = password_bytes.decode('utf-8', errors='ignore')

        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate a hash for the given password."""
        import logging
        logger = logging.getLogger(__name__)

        # Bcrypt has a 72-byte limit. Truncate if necessary and log a warning.
        if len(password.encode('utf-8')) > 72:
            logger.warning(f"Password length {len(password.encode('utf-8'))} bytes exceeds bcrypt's 72-byte limit. Truncating.")
            # Truncate to 72 bytes safely (avoid cutting in middle of multi-byte character)
            password_bytes = password.encode('utf-8')[:72]
            password = password_bytes.decode('utf-8', errors='ignore')

        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode a JWT token."""
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload
        except JWTError:
            raise AuthError("Invalid token")

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Authenticate a user by verifying email and password.
        
        Returns:
            tuple: (user_id, tenant_id, email, username) if successful, (None, None, None, None) otherwise.
        """
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Authentication attempt for email: {email}")
            
            
            user = db.query(User).options(joinedload(User.tenant)).filter(User.email == email).first()
            
            if not user:
                logger.info(f"User not found: {email}")
                return None, None, None, None
                
            logger.info(f"User found: {user.email}, status: {user.status}, active: {user.is_active}")
            
            if AuthService.verify_password(password, user.pass_wd_sha):
                logger.info(f"Password verified successfully for {email}")
                # Update last login
                user.last_login_at = datetime.utcnow()
                db.commit()
                return user.user_id, user.tenant_id, user.email, user.user_name
            else:
                logger.info(f"Password verification failed for {email}")
                return None, None, None, None
        except SQLAlchemyError as e:
            logger.error(f"Database error during authentication: {str(e)}")
            raise DatabaseError(f"Database error during authentication: {str(e)}") from e

    @staticmethod
    def get_tenant_info(db: Session, tenant_id: str) -> Optional[str]:
        """Retrieve tenant information based on tenant_id."""
        try:
            tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
            if tenant:
                return tenant.tenant_name
            return None
        except SQLAlchemyError as e:
            raise DatabaseError(f"Database error while fetching tenant info: {str(e)}") from e

    @staticmethod
    def register_user(db: Session, email: str, username: str, password: str, organization: str, 
                     tenant_id: Optional[str] = None, is_first_user: bool = False) -> Tuple[str, str, str]:
        """
        Register a new user and, if necessary, a new tenant.
        
        Args:
            db: Database session
            email: User email
            username: Username
            password: User password
            organization: Organization/tenant name
            tenant_id: Existing tenant ID (for non-first users)
            is_first_user: Whether this is the first user in the system
        
        Returns:
            tuple: (user_id, tenant_id, activation_code)
        """
        try:
            # Check if user exists
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                # Check activation status (both models now have status column)
                is_activated = existing_user.status == 'A'
                is_not_activated = existing_user.status == 'N'
                
                # If user exists but is not activated, update their info and resend activation code
                if is_not_activated:
                    # Generate new activation code
                    new_activation_code = AuthService.generate_activation_code()
                    
                    # Update user information
                    existing_user.user_name = username
                    existing_user.pass_wd_sha = AuthService.get_password_hash(password)
                        
                    existing_user.activation_code = new_activation_code
                    
                    db.commit()
                    return existing_user.user_id, existing_user.tenant_id, new_activation_code
                else:
                    raise AuthError("Email already exists")

            # First user: create their tenant from the organization name they
            # registered with (same naming rules as every later sign-up)
            if is_first_user:
                new_tenant = AuthService.create_tenant_for_user(db, username, email, organization)
                tenant_id = new_tenant.tenant_id

                # Set user role to INSTANCE_ADMIN
                user_role = UserRole.INSTANCE_ADMIN
                user_status = 'A'  # First user is automatically activated
                user_is_active = True
            else:
                # For subsequent users, tenant_id can be provided or auto-created
                if tenant_id:
                    # Verify tenant exists if provided
                    existing_tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
                    if not existing_tenant:
                        raise AuthError("Invalid tenant ID")

                    # Default role for users joining existing tenant
                    user_role = UserRole.FLOW_DESIGNER
                    user_status = 'N'  # Users need activation
                    user_is_active = False
                else:
                    # Auto-create tenant for user using common method
                    new_tenant = AuthService.create_tenant_for_user(db, username, email, organization)
                    tenant_id = new_tenant.tenant_id

                    # User creating their own tenant becomes TENANT_ADMIN
                    user_role = UserRole.TENANT_ADMIN
                    user_status = 'N'  # Users need activation
                    user_is_active = False

            # Generate IDs
            user_id = str(uuid.uuid4())
            activation_code = AuthService.generate_activation_code()

            # Create user
            new_user = User(
                user_id=user_id,
                user_name=username,
                email=email,
                auth_provider='email',
                pass_wd_sha=AuthService.get_password_hash(password),
                status=user_status,
                acct_lock='N',
                activation_code=activation_code,
                tenant_id=tenant_id,
                role=user_role,
                is_active=user_is_active
            )
            db.add(new_user)
            
            # Update tenant owner for first user or auto-created tenant
            if is_first_user or (not is_first_user and 'new_tenant' in locals()):
                new_tenant.user_id_own = user_id

            db.commit()

            # Create tenant schema and tables for first user or auto-created tenant
            if 'new_tenant' in locals():
                from db.database import create_schema, create_tenant_tables
                create_schema(new_tenant.schema_name)
                create_tenant_tables(new_tenant.schema_name)

            return user_id, tenant_id, activation_code

        except IntegrityError as e:
            db.rollback()
            raise AuthError("Email already exists") from e
        except SQLAlchemyError as e:
            db.rollback()
            raise DatabaseError(f"Database error during user registration: {str(e)}") from e

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[dict]:
        """Retrieve a user based on their email address."""
        try:
            user = db.query(User).options(joinedload(User.tenant)).filter(User.email == email).first()
            if user:
                return {
                    'user_id': user.user_id,
                    'email': user.email,
                    'user_name': user.user_name,
                    'status': user.status,
                    'activation_code': user.activation_code,
                    'role': user.role.value if user.role else None,
                    'tenant': {
                        'tenant_id': user.tenant.tenant_id,
                        'tenant_name': user.tenant.tenant_name,
                        'schema_name': user.tenant.schema_name
                    } if user.tenant else None
                }
            return None
        except SQLAlchemyError as e:
            raise DatabaseError(f"Database error while fetching user: {str(e)}") from e

    @staticmethod
    def activate_user(db: Session, email: str, activation_code: str) -> bool:
        """Activate a user's account."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            logger.info(f"activate_user called for email: {email}, code: {activation_code}")
            user = db.query(User).filter(User.email == email).first()
            if not user:
                logger.error(f"User not found: {email}")
                raise AuthError("User not found")

            logger.info(f"Found user - stored activation_code: {user.activation_code}, provided: {activation_code}")
            if user.activation_code != activation_code:
                logger.error(f"Activation code mismatch for {email}")
                raise AuthError("Invalid activation code")

            # Activate user
            logger.info(f"Activating user {email} - setting status='A' and is_active=True")
            user.status = 'A'
            user.is_active = True
            user.activation_code = None
            db.commit()
            logger.info(f"User {email} activated successfully - status: {user.status}, is_active: {user.is_active}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Database error during activation: {str(e)}")
            db.rollback()
            raise DatabaseError(f"Database error during user activation: {str(e)}") from e

    @staticmethod
    def update_password(db: Session, email: str, new_password: str) -> bool:
        """Update a user's password."""
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                raise AuthError("User not found")
            
            # Update password
            user.pass_wd_sha = AuthService.get_password_hash(new_password)
                
            db.commit()
            return True
        except SQLAlchemyError as e:
            db.rollback()
            raise DatabaseError(f"Database error during password update: {str(e)}") from e

    @staticmethod
    def generate_activation_code(length: int = 6) -> str:
        """Generate a random activation code."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    @staticmethod
    def create_tenant_for_user(db: Session, username: str, email: str, organization: str = None) -> Tenant:
        """
        Create a new tenant for a user with automatic name generation.

        Args:
            db: Database session
            username: Username for generating tenant name
            email: User's email for extracting domain
            organization: Organization name provided by user (optional)

        Returns:
            Tenant: The newly created tenant (not yet committed)
        """
        tenant_id = str(uuid.uuid4())
        tenant_name = organization if organization else f"{username}'s organization"

        # Ensure tenant name is unique
        base_tenant_name = tenant_name
        counter = 1
        while db.query(Tenant).filter(Tenant.tenant_name == tenant_name).first():
            tenant_name = f"{base_tenant_name}_{counter}"
            counter += 1

        # Generate schema name from tenant name
        schema_name = f"tenant_{tenant_name.lower().replace(' ', '_')}"
        # Remove apostrophes separately
        schema_name = schema_name.replace("'", "")

        # Ensure schema name is unique
        base_schema = schema_name
        counter = 1
        while db.query(Tenant).filter(Tenant.schema_name == schema_name).first():
            schema_name = f"{base_schema}_{counter}"
            counter += 1

        # Create tenant
        new_tenant = Tenant(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            schema_name=schema_name,
            email_domain=email.split('@')[1],
            user_id_own=None  # Will be updated after user creation
        )

        db.add(new_tenant)
        db.flush()  # Get the tenant_id without committing

        return new_tenant

    @staticmethod
    def get_current_user(db: Session, token: str) -> Optional[User]:
        """Get the current user from JWT token."""
        try:
            payload = AuthService.decode_token(token)
            user_id = payload.get("sub")
            if user_id is None:
                raise AuthError("Invalid token")
            
            user = db.query(User).options(joinedload(User.tenant)).filter(User.user_id == user_id).first()
            if user is None:
                raise AuthError("User not found")
            
            return user
        except JWTError:
            raise AuthError("Invalid token")