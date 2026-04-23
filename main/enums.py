from enum import Enum

class TipMethodType(Enum):
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    
    def __str__(self):
        return self.name
    
    def __repr__(self):
        return self.name
      

