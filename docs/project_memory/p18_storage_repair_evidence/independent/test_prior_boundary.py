"""Import the byte-identical archived independent class, without modifying it."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent/'p18-persistence-review-20260913'))
from test_independent_persistence import IndependentPersistenceTests
