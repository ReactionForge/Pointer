"""Generate all default cursor assets from the shared drawing code."""
def main():
 from pointer.cursor.art import arrow, hand, roles, palette, frames
 for module in (arrow, hand, roles, palette, frames): module.main()
if __name__ == "__main__": main()
