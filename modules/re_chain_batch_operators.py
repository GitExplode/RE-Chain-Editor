#Batch chain version converter operator (added to RE Chain Editor)
import bpy
import os

from bpy.types import Operator

from .blender_utils import showMessageBox
from .re_chain_batch_convert import batchConvertChainFiles


class WM_OT_BatchConvertChainVersion(Operator):
	bl_label = "Batch Convert Chain Version (54 to 55)"
	bl_idname = "re_chain.batch_convert_version"
	bl_description = "Converts all .chain.54 files in the chosen folder to .chain.55.\nOnly the version number is changed. Each file is checked with the chain reader before and after, and the original files are kept"
	bl_options = {'REGISTER'}
	
	dirPath : bpy.props.StringProperty(
		name = "Directory",
		description = "Folder containing the .chain.54 files to convert",
		default = "",
		subtype = "DIR_PATH",)
	
	searchSubdirectories : bpy.props.BoolProperty(
		name = "Search Subdirectories",
		description = "Also convert .chain.54 files inside folders within the chosen directory",
		default = True,
		)
	
	overwriteExisting : bpy.props.BoolProperty(
		name = "Overwrite Existing .chain.55 Files",
		description = "If a .chain.55 file already exists next to a .chain.54 file, replace it. When off, those files are skipped",
		default = False,
		)
	
	def execute(self,context):
		directory = bpy.path.abspath(self.dirPath)
		if not os.path.isdir(directory):
			showMessageBox("Choose a valid directory.",title = "Chain Version Converter",icon = "ERROR")
			return {'CANCELLED'}
		
		results = batchConvertChainFiles(directory,searchSubdirectories = self.searchSubdirectories,overwrite = self.overwriteExisting,srcVersion = 54,dstVersion = 55)
		convertedCount = len(results["converted"])
		existsCount = len(results["exists"])
		failedCount = len(results["failed"])
		totalCount = convertedCount + existsCount + failedCount
		
		if totalCount == 0:
			message = "No .chain.54 files found."
			showMessageBox(message,title = "Chain Version Converter",icon = "INFO")
			self.report({"INFO"},message)
			return {'FINISHED'}
		
		message = f"Converted {convertedCount} of {totalCount} chain files."
		if existsCount:
			message += f" {existsCount} skipped (.chain.55 already exists)."
		if failedCount:
			message += f" {failedCount} failed, see Window > Toggle System Console."
		showMessageBox(message,title = "Chain Version Converter",icon = "ERROR" if failedCount else "INFO")
		self.report({"WARNING"} if failedCount else {"INFO"},message)
		return {'FINISHED'}
	
	def invoke(self,context,event):
		if self.dirPath == "":
			if "modWorkspace_directory" in context.scene:#Mod directory set by the RE Asset Library / RE Mesh Editor workspace, if it's there
				self.dirPath = context.scene["modWorkspace_directory"]
			elif bpy.data.filepath != "":
				self.dirPath = os.path.dirname(bpy.data.filepath)
		try:
			return context.window_manager.invoke_props_dialog(self,width = 500,confirm_text = "Convert Chain Files")
		except TypeError:#confirm_text isn't available on older Blender versions
			return context.window_manager.invoke_props_dialog(self,width = 500)
	
	def draw(self,context):
		layout = self.layout
		layout.label(text = "Converts .chain.54 files to .chain.55.")
		layout.label(text = "Only the version number changes. Original files are kept.")
		layout.prop(self,"dirPath")
		layout.prop(self,"searchSubdirectories")
		layout.prop(self,"overwriteExisting")
