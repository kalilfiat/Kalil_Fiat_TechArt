Hook Tools is a Blender addon that simplifies the creation and management of hooks on curve splines. It lets you generate empties and hook modifiers quickly, with control over shape, size, and automatic organization.

Features

Create one hook per selected point
Or create a single hook for multiple selected points
Automatically generates empties
Customizable empty shape and size
Automatically organizes hooks into a collection:
Hooks_<ParentCollectionName>
Safe removal of hooks and related empties
Automatically removes empty collections when no longer needed

Installation

Open Blender
Go to Edit > Preferences > Add-ons
Click Install
Select the .py file
Enable "Hook Tools"

Usage

Create Hooks

Select a curve object
Enter Edit Mode
Select one or more points
Open the sidebar (N) → Hook Tools
Adjust:
Empty shape
Empty size
Single Hook Mode (optional)
Click "Create Hooks"

Remove Hooks

Select the curve object
Open Hook Tools
Click "Remove Hooks"

This will remove all hook modifiers, delete associated empties, and clean up empty collections if needed.

Notes

Works with Bezier, Poly, and NURBS curves
If the object belongs to multiple collections, the first one is used as reference
Designed for clean and fast spline workflows

Version

1.1.0