"""
Sollumz Hierarchy Validator

This module provides functions to validate the hierarchical structure of Sollumz objects
and provide helpful error messages when the hierarchy is incorrect.
"""

import bpy
from typing import List, Tuple, Optional
from .sollumz_properties import (
    SollumType, 
    BOUND_TYPES, 
    BOUND_POLYGON_TYPES,
    DRAWABLE_TYPES,
    FRAGMENT_TYPES
)
from .tools.blenderhelper import get_children_recursive
from . import logger


class HierarchyError:
    """Represents a hierarchy validation error with a helpful message."""
    
    def __init__(self, obj: bpy.types.Object, message: str, suggestion: str = ""):
        self.obj = obj
        self.message = message
        self.suggestion = suggestion
    
    def __str__(self):
        msg = f"Hierarchy error for '{self.obj.name}': {self.message}"
        if self.suggestion:
            msg += f" Suggestion: {self.suggestion}"
        return msg


def validate_drawable_hierarchy(drawable_obj: bpy.types.Object) -> List[HierarchyError]:
    """
    Validate the hierarchy of a Drawable object.
    
    Expected hierarchy:
    - Drawable → Drawable Model (for visual meshes)
    - Drawable → Light (for lights)
    - Drawable → Bound Composite → Bound shapes (for embedded collision)
    """
    errors = []
    
    if drawable_obj.sollum_type != SollumType.DRAWABLE:
        return errors
    
    for child in drawable_obj.children:
        child_type = child.sollum_type
        
        # Check for invalid direct children
        if child_type in BOUND_POLYGON_TYPES:
            errors.append(HierarchyError(
                child,
                f"Bound polygon objects (like {child_type}) cannot be direct children of a Drawable",
                "Move this bound polygon under a Bound Composite object"
            ))
        elif child_type in BOUND_TYPES and child_type != SollumType.BOUND_COMPOSITE:
            errors.append(HierarchyError(
                child,
                f"Bound objects (like {child_type}) should not be direct children of a Drawable",
                "Create a Bound Composite parent or move to proper collision hierarchy"
            ))
        elif child_type == SollumType.DRAWABLE_GEOMETRY:
            errors.append(HierarchyError(
                child,
                "Drawable Geometry objects cannot be direct children of a Drawable",
                "Drawable Geometry should be under a Drawable Model"
            ))
        elif child_type in FRAGMENT_TYPES:
            errors.append(HierarchyError(
                child,
                f"Fragment objects (like {child_type}) cannot be children of a Drawable",
                "Fragment objects should be under a Fragment parent, not a Drawable"
            ))
        
        # Valid children: DRAWABLE_MODEL, LIGHT, BOUND_COMPOSITE, SKELETON
        # Continue validation for bound composites
        if child_type == SollumType.BOUND_COMPOSITE:
            errors.extend(validate_bound_composite_hierarchy(child))
    
    return errors


def validate_bound_composite_hierarchy(bound_composite_obj: bpy.types.Object) -> List[HierarchyError]:
    """
    Validate the hierarchy of a Bound Composite object.
    
    Expected hierarchy:
    - Bound Composite → Bound shapes/geometries
    """
    errors = []
    
    if bound_composite_obj.sollum_type != SollumType.BOUND_COMPOSITE:
        return errors
    
    for child in bound_composite_obj.children:
        child_type = child.sollum_type
        
        # Check for invalid children
        if child_type == SollumType.DRAWABLE_MODEL:
            errors.append(HierarchyError(
                child,
                "Drawable Models cannot be children of a Bound Composite",
                "Move this Drawable Model under a Drawable object"
            ))
        elif child_type in DRAWABLE_TYPES and child_type != SollumType.DRAWABLE:
            errors.append(HierarchyError(
                child,
                f"Drawable objects (like {child_type}) cannot be children of a Bound Composite",
                "Check your hierarchy structure"
            ))
        elif child_type in FRAGMENT_TYPES:
            errors.append(HierarchyError(
                child,
                f"Fragment objects (like {child_type}) cannot be children of a Bound Composite",
                "Fragment objects should be under a Fragment parent"
            ))
    
    return errors


def validate_fragment_hierarchy(fragment_obj: bpy.types.Object) -> List[HierarchyError]:
    """
    Validate the hierarchy of a Fragment object.
    
    Expected hierarchy:
    - Fragment → FragGroup/FragChild
    - FragGroup → Drawable Models, Bound Composite
    """
    errors = []
    
    if fragment_obj.sollum_type != SollumType.FRAGMENT:
        return errors
    
    for child in fragment_obj.children:
        child_type = child.sollum_type
        
        # Check for invalid direct children
        if child_type == SollumType.DRAWABLE_MODEL:
            errors.append(HierarchyError(
                child,
                "Drawable Models cannot be direct children of a Fragment",
                "Put Drawable Models under a FragGroup or FragChild"
            ))
        elif child_type in BOUND_TYPES:
            errors.append(HierarchyError(
                child,
                f"Bound objects (like {child_type}) cannot be direct children of a Fragment",
                "Put Bound objects under a FragGroup or FragChild"
            ))
    
    return errors


def validate_clip_dictionary_hierarchy(clip_dict_obj: bpy.types.Object) -> List[HierarchyError]:
    """
    Validate the hierarchy of a Clip Dictionary object.
    
    Expected hierarchy:
    - Clip Dictionary → Clips → Clip
    """
    errors = []
    
    if clip_dict_obj.sollum_type != SollumType.CLIP_DICTIONARY:
        return errors
    
    for child in clip_dict_obj.children:
        child_type = child.sollum_type
        
        # Check for invalid direct children
        if child_type == SollumType.CLIP:
            errors.append(HierarchyError(
                child,
                "Clip objects cannot be direct children of a Clip Dictionary",
                "Put Clip objects under a Clips container"
            ))
        elif child_type not in [SollumType.CLIPS, SollumType.ANIMATIONS]:
            errors.append(HierarchyError(
                child,
                f"'{child_type}' objects are not valid children of a Clip Dictionary",
                "Only Clips and Animations containers should be direct children"
            ))
    
    return errors


def validate_object_hierarchy(obj: bpy.types.Object) -> List[HierarchyError]:
    """
    Validate the hierarchy of a single Sollumz object and all its children.
    """
    errors = []
    
    # Validate based on object type
    if obj.sollum_type == SollumType.DRAWABLE:
        errors.extend(validate_drawable_hierarchy(obj))
    elif obj.sollum_type == SollumType.BOUND_COMPOSITE:
        errors.extend(validate_bound_composite_hierarchy(obj))
    elif obj.sollum_type == SollumType.FRAGMENT:
        errors.extend(validate_fragment_hierarchy(obj))
    elif obj.sollum_type == SollumType.CLIP_DICTIONARY:
        errors.extend(validate_clip_dictionary_hierarchy(obj))
    
    # Recursively validate children
    for child in obj.children:
        errors.extend(validate_object_hierarchy(child))
    
    return errors


def validate_scene_hierarchies() -> List[HierarchyError]:
    """
    Validate all Sollumz object hierarchies in the current scene.
    """
    errors = []
    
    # Find all top-level Sollumz objects
    top_level_sollumz = [
        obj for obj in bpy.context.scene.objects 
        if obj.parent is None and hasattr(obj, 'sollum_type') and obj.sollum_type != SollumType.NONE
    ]
    
    for obj in top_level_sollumz:
        errors.extend(validate_object_hierarchy(obj))
    
    return errors


def check_hierarchy_before_export(obj: bpy.types.Object) -> Tuple[bool, List[str]]:
    """
    Check if an object has valid hierarchy before export.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = validate_object_hierarchy(obj)
    
    if not errors:
        return True, []
    
    error_messages = []
    for error in errors:
        error_messages.append(str(error))
        logger.error(str(error))
    
    return False, error_messages


def log_hierarchy_suggestions(obj: bpy.types.Object) -> None:
    """
    Log helpful suggestions when no materials are found, 
    checking if it might be a hierarchy issue.
    """
    errors = validate_object_hierarchy(obj)
    
    if errors:
        logger.warning(f"Detected hierarchy issues that might explain missing materials:")
        for error in errors[:3]:  # Limit to first 3 errors to avoid spam
            logger.warning(f"  • {error}")
        
        if len(errors) > 3:
            logger.warning(f"  • ... and {len(errors) - 3} more hierarchy issues")
        
        logger.info("Fix these hierarchy issues and try exporting again.")
    else:
        # Check if there are children that might need to be models
        drawable_children = [child for child in obj.children if child.type == "MESH"]
        if drawable_children:
            logger.info(f"Found {len(drawable_children)} mesh children. Consider converting them to Drawable Models using 'Convert to Drawable Model' if they should be visual meshes.")