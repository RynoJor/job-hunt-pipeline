"""Job-hunt pipeline: source, enrich, score and shortlist remote job ads."""
from .remote import RemoteVerdict, check_remote_eligibility

__all__ = ["RemoteVerdict", "check_remote_eligibility"]
__version__ = "0.1.0"
