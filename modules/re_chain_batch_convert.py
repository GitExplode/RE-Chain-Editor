#Batch chain version converter (added to RE Chain Editor)
#
#Converts .chain.54 files to .chain.55 by changing ONLY the version number in the header of the original file.
#Every file is parsed with this addon's own chain reader before and after the change, so anything the
#reader can't understand is skipped and reported instead of being written.
#A .chain.55 file is always written (overwriting one that's already there). The original .chain.54 file is
#then either renamed to .chain.54.bak to keep it as a backup, or removed, controlled by the keepBackup option.
#
#Why only the version number: the chain layout is the same in versions 54 and 55 (this addon already uses the same
#structure sizes for both, see SIZE_DATA "ver >= 53" in file_re_chain.py), and a real .chain.54 / .chain.55 pair
#for an armor differed by that one value only. The game's own hair files did change some physics values
#between the two versions, those are tuning changes by the developers and are intentionally left alone here.
#
#This file does not import bpy, so it can be tested outside of Blender.

import os
import io
import struct
import contextlib

from .file_re_chain import ChainFile
from .gen_functions import textColors

#Source version -> target version
SUPPORTED_CONVERSIONS = {54:55}


class _StrictReader(io.BytesIO):
	"""Raises an error if the reader tries to read past the end of the data.
	Needed because read_unicode_string() in gen_functions.py loops forever when it hits the end of a file without finding a terminator,
	which would freeze Blender on a truncated or corrupt file."""
	def read(self,size = -1):
		data = super().read(size)
		if size is not None and size >= 0 and len(data) < size:
			raise EOFError("tried to read past the end of the file")
		return data


def _checkChainBytes(data,expectedVersion):
	"""Parses the data with the chain editor's reader. Returns None if it's fine, otherwise a string describing the problem."""
	if len(data) < 0x70:
		return "file is too small to be a chain file"
	if data[4:8] != b"chan":
		return "file is not a chain file"
	fileVersion = struct.unpack_from("<I",data,0)[0]
	if fileVersion != expectedVersion:
		return f"file is version {fileVersion}, expected {expectedVersion}"
	chainFile = ChainFile()
	try:
		with contextlib.redirect_stdout(io.StringIO()):#The reader prints a lot, keep the console readable during batch runs
			chainFile.read(_StrictReader(data))
	except Exception as err:
		return f"chain reader failed: {err}"
	header = chainFile.Header
	if header.version != expectedVersion:
		return f"reader saw version {header.version}, expected {expectedVersion}"
	offsets = {
		"collisionAttrAssetOffset":header.collisionAttrAssetOffset,
		"chainModelCollisionOffset":header.chainModelCollisionOffset,
		"extraDataOffset":header.extraDataOffset,
		"chainGroupOffset":header.chainGroupOffset,
		"chainLinkOffset":header.chainLinkOffset,
		"chainSettingsOffset":header.chainSettingsOffset,
		"chainWindSettingsOffset":header.chainWindSettingsOffset,
		}
	for name,offset in offsets.items():
		if offset > len(data):
			return f"{name} points past the end of the file"
	if (len(chainFile.ChainSettingsList) != header.chainSettingsCount
		or len(chainFile.ChainGroupList) != header.chainGroupCount
		or len(chainFile.ChainCollisionList) != header.chainModelCollisionCount
		or len(chainFile.WindSettingsList) != header.chainWindSettingsCount
		or len(chainFile.ChainLinkList) != header.chainLinkCount):
		return "entry counts in the header don't match what was read"
	return None


def convertChainFile(srcPath,dstPath,srcVersion = 54,dstVersion = 55,keepBackup = True):
	"""Returns (status,message). Status is "converted" or "failed".
	The .chain.<dstVersion> file is always written, overwriting one that's already there.
	When keepBackup is True the .chain.<srcVersion> file is renamed to .chain.<srcVersion>.bak (overwriting an existing .bak file), so it's kept as a backup of the original.
	When keepBackup is False the .chain.<srcVersion> file is removed once the new file has been written, so the file is just updated in place."""
	if SUPPORTED_CONVERSIONS.get(srcVersion) != dstVersion:
		return ("failed",f"converting {srcVersion} to {dstVersion} is not supported")
	try:
		with open(srcPath,"rb") as file:
			data = file.read()
	except Exception as err:
		return ("failed",f"couldn't read file: {err}")
	
	problem = _checkChainBytes(data,srcVersion)
	if problem != None:
		return ("failed",problem)
	
	newData = bytearray(data)
	struct.pack_into("<I",newData,0,dstVersion)
	newData = bytes(newData)
	
	problem = _checkChainBytes(newData,dstVersion)
	if problem != None:
		return ("failed",f"converted data didn't pass the check: {problem}")
	
	tempPath = dstPath + ".tmp"
	try:
		with open(tempPath,"wb") as file:
			file.write(newData)
		os.replace(tempPath,dstPath)
	except Exception as err:
		try:
			if os.path.exists(tempPath):
				os.remove(tempPath)
		except Exception:
			pass
		return ("failed",f"couldn't write file: {err}")
	
	if keepBackup:
		backupPath = srcPath + ".bak"
		try:
			os.replace(srcPath,backupPath)#Renames, overwriting an existing .bak file
		except Exception as err:
			return ("converted",f"converted, but couldn't rename the old .chain.{srcVersion} file to .bak: {err}")
	else:
		try:
			os.remove(srcPath)
		except Exception as err:
			return ("converted",f"converted, but couldn't remove the old .chain.{srcVersion} file: {err}")
	return ("converted","")


def findChainFiles(directory,version,searchSubdirectories = True):
	suffix = f".chain.{version}"
	foundList = []
	if searchSubdirectories:
		for root,dirs,files in os.walk(directory):
			for fileName in files:
				if fileName.lower().endswith(suffix):
					foundList.append(os.path.join(root,fileName))
	else:
		for fileName in os.listdir(directory):
			path = os.path.join(directory,fileName)
			if os.path.isfile(path) and fileName.lower().endswith(suffix):
				foundList.append(path)
	return sorted(foundList)


def batchConvertChainFiles(directory,searchSubdirectories = True,keepBackup = True,srcVersion = 54,dstVersion = 55):
	"""Converts every .chain.<srcVersion> file in the directory, overwriting a .chain.<dstVersion> file that's already there.
	When keepBackup is True the .chain.<srcVersion> files are renamed to .chain.<srcVersion>.bak as backups. When False they're removed after a successful conversion.
	Returns a dict with lists of (path,message) for "converted" and "failed"."""
	results = {"converted":[],"failed":[]}
	fileList = findChainFiles(directory,srcVersion,searchSubdirectories)
	print(f"{textColors.OKCYAN}Converting {len(fileList)} .chain.{srcVersion} files to .chain.{dstVersion}...{textColors.ENDC}")
	for srcPath in fileList:
		dstPath = srcPath[:-len(str(srcVersion))] + str(dstVersion)#Keeps the original casing of the rest of the name
		status,message = convertChainFile(srcPath,dstPath,srcVersion,dstVersion,keepBackup)
		results[status].append((srcPath,message))
		if status == "converted":
			print(f"{textColors.OKGREEN}Converted{textColors.ENDC} {srcPath}")
		else:
			print(f"{textColors.FAIL}Failed{textColors.ENDC} {srcPath}: {message}")
	print(f"Done. {len(results['converted'])} converted, {len(results['failed'])} failed.")
	return results
