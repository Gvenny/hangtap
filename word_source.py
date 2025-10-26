import random
from pathlib import Path
from typing import List, Optional

class WordSource:
    """
    Manages loading and providing words for the game from a word list file.
    """

    def __init__(self, word_file_path: Path):
        """
        Initializes the WordSource with a path to a word list file.

        Args:
            word_file_path: The path to the file containing words, one per line.
        """
        if not word_file_path.is_file():
            raise FileNotFoundError(f"Word file not found at: {word_file_path}")
        self.word_file_path = word_file_path
        self._words: List[str] = self._load_words()

    def _load_words(self) -> List[str]:
        """Loads and cleans words from the specified file."""
        with open(self.word_file_path, 'r', encoding='utf-8') as f:
            words = [
                line.strip().lower()
                for line in f
                if line.strip().isalpha()
            ]
        if not words:
            raise ValueError(f"No valid words found in {self.word_file_path}")
        return words

    def get_random_word(
        self, min_length: int = 0, max_length: Optional[int] = None
    ) -> str:
        """
        Gets a random word from the list, optionally filtered by length.

        Args:
            min_length: The minimum length of the word.
            max_length: The maximum length of the word. If None, no upper limit.

        Returns:
            A random word matching the criteria.

        Raises:
            ValueError: If no words match the specified length criteria.
        """
        filtered_words = self._words

        if min_length > 0:
            filtered_words = [w for w in filtered_words if len(w) >= min_length]

        if max_length is not None:
            filtered_words = [w for w in filtered_words if len(w) <= max_length]

        if not filtered_words:
            raise ValueError("No words available matching the specified criteria.")

        return random.choice(filtered_words)

    def __len__(self) -> int:
        """Returns the total number of words loaded."""
        return len(self._words)
