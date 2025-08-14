"""
Script Name: Change Case
Script Version: 0.1
Flame Version: 2023
Author: Kyle Obley (info@kyleobley.com)

Creation date: 14.08.25
Modified date: 14.08.25

Description:

Takes the existing name of a sequence or clip and changes the case to UPPERCASE, lowercase or PascalCase.

Chnage Log:

    v0.1: Initial Release

"""

def to_pascal_case(text):
    """
    Convert a string to PascalCase while preserving all characters.
    Capitalizes the first letter of every word including the first word.
    
    Args:
        text (str): Input string that may contain spaces, special characters, and numbers
        
    Returns:
        str: String converted to PascalCase with all original characters preserved
    """
    if not text:
        return ""
    
    result = []
    at_word_start = True
    
    for char in text:
        if char.isalpha():
            if at_word_start:
                # Capitalize first letter of every word (including first word)
                result.append(char.upper())
                at_word_start = False
            else:
                # Middle of word - keep lowercase
                result.append(char.lower())
        else:
            # Non-letter characters (spaces, special chars, numbers) are preserved
            result.append(char)
            # Mark that we're potentially at the start of next word
            at_word_start = True
    
    return ''.join(result)

def change_case_upper(selection):
    """
    Convert a string to UPPERCASE
    """

    for item in selection:
        current_name = str(item.name.get_value())
        new_name = current_name.upper()
        item.name.set_value(new_name)

def change_case_lower(selection):
    """
    Convert a string to lowercase
    """

    for item in selection:
        current_name = str(item.name.get_value())
        new_name = current_name.lower()
        item.name.set_value(new_name)

def change_case_pascal(selection):
    """
    Convert a string to PascalCase
    """

    for item in selection:
        current_name = str(item.name.get_value())
        new_name = to_pascal_case(current_name)
        item.name.set_value(new_name)

# Scoping
def clip_selected(selection):
    import flame
    for item in selection:
        if isinstance(item, (flame.PySequence, flame.PyClip)):
            return True
    return False


# Flame Media Panel
def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "Renaming Tools",
            "actions": [
                {
                    "name": "Change Case (UPPER)",
                    "isVisable": clip_selected,
                    "isEnabled": clip_selected,
                    "execute": change_case_upper
                },
                {
                    "name": "Change Case (lower)",
                    "isVisable": clip_selected,
                    "isEnabled": clip_selected,
                    "execute": change_case_lower
                },
                {
                    "name": "Change Case (Pascal)",
                    "isVisable": clip_selected,
                    "isEnabled": clip_selected,
                    "execute": change_case_pascal
                }
            ]
        }
    ]