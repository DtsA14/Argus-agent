"""Product decisions about customer names. Owned by the product team, not by engineering."""

# Which part of a multi-part name is the surname used for sorting has NOT been decided yet.
# The two candidates under discussion, both used by other products:
#   "last-token":    "Ana Maria Garcia Lopez" sorts under "Lopez",  "Ludwig van Beethoven" under "Beethoven"
#   "first-surname": "Ana Maria Garcia Lopez" sorts under "Garcia", "Ludwig van Beethoven" under "van Beethoven"
# The product team will set this. Until then it stays None.
SURNAME_RULE = None
