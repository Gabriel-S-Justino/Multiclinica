from typing import Annotated

from pydantic import StringConstraints

from backend.application.contracts import Command

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ()-]{8,24}$")]
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"),
]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class PersonalDetails(Command):
    full_name: Name
    email: Email
    phone: Phone
    job_title: ShortText | None = None
    professional_registration: ShortText | None = None


class ClinicDetails(Command):
    legal_name: Name
    document: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            pattern=r"^(?:[0-9]{14}|[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2})$",
        ),
    ]
    responsible_name: Name
    email: Email
    phone: Phone
    postal_code: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{5}-?[0-9]{3}$")
    ]
    address: ShortText
    address_number: ShortText
    complement: ShortText | None = None
    neighborhood: ShortText
    city: ShortText
    state: Annotated[
        str,
        StringConstraints(
            pattern=r"^(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$"
        ),
    ]
