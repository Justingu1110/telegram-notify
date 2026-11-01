from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    price: str
    url: str
    shipping: str
