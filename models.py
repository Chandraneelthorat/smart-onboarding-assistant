from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship
from database import Base


class Employee(Base):
    __tablename__ = "employees"

    emp_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    manager_id = Column(String, ForeignKey("employees.emp_id"), nullable=True)
    email = Column(String, nullable=True)
    onboarding_status = Column(String(32), nullable=False, default="Active")
    created_at = Column(DateTime, nullable=True, server_default=func.now())

    manager = relationship(
        "Employee",
        remote_side="Employee.emp_id",
        foreign_keys=[manager_id],
    )
    direct_reports = relationship(
        "Employee",
        foreign_keys=[manager_id],
        overlaps="manager",
    )
    leave_balance = relationship(
        "LeaveBalance",
        back_populates="employee",
        uselist=False,
        cascade="all, delete-orphan",
    )
    leave_history = relationship(
        "LeaveHistory", back_populates="employee", cascade="all, delete-orphan"
    )
    meetings = relationship(
        "Meeting",
        back_populates="employee",
        foreign_keys="Meeting.emp_id",
        cascade="all, delete-orphan",
    )
    tickets = relationship(
        "Ticket", back_populates="employee", cascade="all, delete-orphan"
    )
    email_logs = relationship("EmailLog", back_populates="employee")
    leave_requests = relationship(
        "LeaveRequest",
        back_populates="employee",
        foreign_keys="LeaveRequest.emp_id",
    )

    def __repr__(self):
        return f"<Employee emp_id={self.emp_id} name={self.name}>"


class Manager(Base):
    """People-leader roster row; `linked_emp_id` ties to the operational `employees` record (tickets, leave, etc.)."""

    __tablename__ = "managers"

    mgr_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    linked_emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=True, index=True)
    onboarding_status = Column(String(32), nullable=False, default="Active")
    created_at = Column(DateTime, nullable=True, server_default=func.now())

    linked_employee = relationship(
        "Employee",
        foreign_keys=[linked_emp_id],
    )

    def __repr__(self):
        return f"<Manager mgr_id={self.mgr_id} name={self.name}>"


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=False, unique=True)
    balance = Column(Integer, nullable=False, default=20)

    employee = relationship("Employee", back_populates="leave_balance")

    def __repr__(self):
        return f"<LeaveBalance emp_id={self.emp_id} balance={self.balance}>"


class LeaveHistory(Base):
    __tablename__ = "leave_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=False)
    leave_date = Column(Date, nullable=False)
    request_id = Column(Integer, nullable=False)

    employee = relationship("Employee", back_populates="leave_history")

    def __repr__(self):
        return f"<LeaveHistory emp_id={self.emp_id} leave_date={self.leave_date}>"


class LeaveRequest(Base):
    """Employee leave application pending HR approval."""

    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    number_of_days = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    message = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="Pending")
    approved_by_emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    employee = relationship(
        "Employee",
        back_populates="leave_requests",
        foreign_keys=[emp_id],
    )
    approver = relationship(
        "Employee",
        foreign_keys=[approved_by_emp_id],
    )


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=False)
    meeting_dt = Column(DateTime, nullable=False)
    topic = Column(String, nullable=False)
    hr_emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=True)
    agenda = Column(Text, nullable=True)
    location_or_link = Column(String(512), nullable=True)
    meeting_status = Column(String(32), nullable=False, default="Scheduled")

    employee = relationship(
        "Employee",
        back_populates="meetings",
        foreign_keys=[emp_id],
    )
    hr_host = relationship(
        "Employee",
        foreign_keys=[hr_emp_id],
    )

    def __repr__(self):
        return f"<Meeting emp_id={self.emp_id} meeting_dt={self.meeting_dt} topic={self.topic}>"


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(String, primary_key=True, index=True)
    emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=False)
    item = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    department = Column(String(128), nullable=True)
    created_by_emp_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="Open")
    closure_notify_pending = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    employee = relationship("Employee", back_populates="tickets")

    def __repr__(self):
        return f"<Ticket ticket_id={self.ticket_id} emp_id={self.emp_id} status={self.status}>"


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(String, ForeignKey("employees.emp_id"), nullable=True, index=True)
    to_addresses = Column(Text, nullable=False)
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    is_html = Column(Boolean, nullable=False, default=False)
    purpose = Column(String(128), nullable=True)
    delivery_status = Column(String(32), nullable=False)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    employee = relationship("Employee", back_populates="email_logs")

    def __repr__(self):
        return f"<EmailLog id={self.id} status={self.delivery_status}>"


class PortalUser(Base):
    __tablename__ = "portal_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False)
    employee_id = Column(String, ForeignKey("employees.emp_id"), nullable=True, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ChatConversation(Base):
    """Persisted OpenRouter chat session (user/assistant turns only)."""

    __tablename__ = "chat_conversations"

    id = Column(String(36), primary_key=True)
    portal_user_id = Column(Integer, ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=True)
    chat_role = Column(String(16), nullable=False)
    employee_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        String(36),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq = Column(Integer, nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portal_user_id = Column(Integer, ForeignKey("portal_users.id"), nullable=True)
    role = Column(String(16), nullable=False)
    employee_id = Column(String, nullable=True)
    tool_name = Column(String(64), nullable=False)
    arguments_json = Column(Text, nullable=True)
    result_preview = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
