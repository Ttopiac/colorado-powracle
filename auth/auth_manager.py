"""
User authentication and session management
"""

import bcrypt
from datetime import datetime
from models.user import User, UserSettings
from db.postgres import get_db


class AuthManager:
    """Handles user registration, login, and session management"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def register_user(email: str, username: str, password: str, home_city: str = "Denver") -> tuple[bool, str, User|None]:
        """
        Register a new user.

        Returns:
            (success: bool, message: str, user: User|None)
        """
        # Validate inputs
        if len(password) < 8:
            return False, "Password must be at least 8 characters", None

        if not email or '@' not in email:
            return False, "Invalid email address", None

        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters", None

        try:
            with get_db() as db:
                # Check if email already exists
                existing_email = db.query(User).filter(User.email == email).first()
                if existing_email:
                    return False, "Email already registered", None

                # Check if username already exists
                existing_username = db.query(User).filter(User.username == username).first()
                if existing_username:
                    return False, "Username already taken", None

                # Create new user
                password_hash = AuthManager.hash_password(password)
                user = User(
                    email=email,
                    username=username,
                    password_hash=password_hash,
                    home_city=home_city
                )
                db.add(user)
                db.flush()  # Get user_id before commit

                # Create default settings
                settings = UserSettings(user_id=user.user_id)
                db.add(settings)

                db.commit()
                db.refresh(user)

                # Expunge user from session to make it independent
                # Access all attributes we need before expunging
                _ = user.username, user.email, user.home_city, user.ski_ability, user.preferred_terrain
                db.expunge(user)

                return True, "Account created successfully!", user

        except Exception as e:
            return False, f"Registration error: {str(e)}", None

    @staticmethod
    def login(email: str, password: str) -> tuple[bool, str, User|None]:
        """
        Authenticate a user.

        Returns:
            (success: bool, message: str, user: User|None)
        """
        try:
            with get_db() as db:
                user = db.query(User).filter(User.email == email).first()

                if not user:
                    return False, "Invalid email or password", None

                if not AuthManager.verify_password(password, user.password_hash):
                    return False, "Invalid email or password", None

                # Update last login
                user.last_login = datetime.utcnow()
                db.commit()
                db.refresh(user)

                # Expunge user from session to make it independent
                # Access all attributes we need before expunging
                _ = user.user_id, user.username, user.email, user.home_city, user.ski_ability, user.preferred_terrain
                db.expunge(user)

                return True, "Login successful!", user

        except Exception as e:
            return False, f"Login error: {str(e)}", None

    @staticmethod
    def get_user_by_id(user_id: str) -> User|None:
        """Get user by ID"""
        try:
            with get_db() as db:
                return db.query(User).filter(User.user_id == user_id).first()
        except Exception:
            return None

    @staticmethod
    def update_profile(user_id: str, **kwargs) -> tuple[bool, str]:
        """
        Update user profile.

        Allowed fields: username, home_city, ski_ability, preferred_terrain
        """
        allowed_fields = ['username', 'home_city', 'ski_ability', 'preferred_terrain']

        try:
            with get_db() as db:
                user = db.query(User).filter(User.user_id == user_id).first()
                if not user:
                    return False, "User not found"

                # Update only allowed fields
                for field, value in kwargs.items():
                    if field in allowed_fields and value is not None:
                        setattr(user, field, value)

                db.commit()
                return True, "Profile updated successfully!"

        except Exception as e:
            return False, f"Update error: {str(e)}"
