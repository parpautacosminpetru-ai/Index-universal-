"""Main entry for Windows executable. No internet or cloud access is used."""
import os
from pathlib import Path
from index_universal.gui import IndexUniversal


def data_home():
    override=os.environ.get("INDEX_UNIVERSAL_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home()/"Documents"/"IndexUniversal"


def main():
    base=data_home()
    app=IndexUniversal(base)
    app.mainloop()


if __name__=="__main__":
    main()
