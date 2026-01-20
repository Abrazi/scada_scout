
import os
import zipfile
import tarfile
import tempfile
import shutil
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

class ArchiveExtractor:
    """Helper class to handle archive files (zip, tar, etc.)"""
    
    SUPPORTED_EXTENSIONS = ['*.scd', '*.cid', '*.icd', '*.xml', '*.zip', '*.tar', '*.tar.gz', '*.tgz', '*.7z', '*.rar', '*.sz']
    ARCHIVE_EXTENSIONS = {'.zip', '.tar', '.gz', '.tgz', '.7z', '.rar', '.sz'}

    @staticmethod
    def is_archive(path: str) -> bool:
        """Check if file is a supported archive."""
        _, ext = os.path.splitext(path.lower())
        return ext in ArchiveExtractor.ARCHIVE_EXTENSIONS

    @staticmethod
    def list_files(path: str) -> List[str]:
        """List files inside an archive. Returns list of filenames."""
        _, ext = os.path.splitext(path.lower())
        files = []
        
        try:
            if ext == '.zip':
                with zipfile.ZipFile(path, 'r') as zf:
                    files = zf.namelist()
            elif ext in ('.tar', '.gz', '.tgz'):
                with tarfile.open(path, 'r') as tf:
                    files = tf.getnames()
            elif ext == '.7z':
                try:
                    import py7zr
                    with py7zr.SevenZipFile(path, mode='r') as z:
                        files = z.getnames()
                except ImportError:
                    logger.error("py7zr not installed")
            elif ext == '.rar':
                try:
                    import rarfile
                    with rarfile.RarFile(path) as rf:
                        files = rf.namelist()
                except ImportError:
                    logger.error("rarfile not installed")
                except rarfile.RarExecError:
                    logger.error("unrar executable not found in PATH")
            elif ext == '.sz':
                # Snappy is single file compression.
                # Use cramjam if available.
                try:
                    base_name = os.path.basename(path)
                    # Remove .sz extension for the inner filename
                    if base_name.lower().endswith('.sz'):
                        files.append(base_name[:-3])
                    else:
                        files.append(base_name + ".decoded")
                except Exception:
                    pass
            else:
                # Fallback to patool: patool doesn't return list programmatically easily.
                try:
                    import patoolib
                    with tempfile.TemporaryDirectory() as td:
                         patoolib.extract_archive(path, outdir=td, verbosity=-1)
                         for root, dirs, filenames in os.walk(td):
                             for f in filenames:
                                 rel_path = os.path.relpath(os.path.join(root, f), td)
                                 files.append(rel_path)
                except Exception as e:
                     # Only log if it's truly unknown
                     pass

        except Exception as e:
            logger.error(f"Failed to list archive {path}: {e}")
            
        return files

    @staticmethod
    def extract_file(archive_path: str, file_to_extract: str, dest_dir: str) -> str:
        """
        Extract specific file from archive to dest_dir. 
        Returns full path to extracted file.
        """
        _, ext = os.path.splitext(archive_path.lower())
        
        try:
            if ext == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extract(file_to_extract, dest_dir)
            elif ext in ('.tar', '.gz', '.tgz'):
                with tarfile.open(archive_path, 'r') as tf:
                    tf.extract(file_to_extract, dest_dir)
            elif ext == '.7z':
                import py7zr
                with py7zr.SevenZipFile(archive_path, mode='r') as z:
                    z.extract(path=dest_dir, targets=[file_to_extract])
            elif ext == '.rar':
                import rarfile
                with rarfile.RarFile(archive_path) as rf:
                    rf.extract(file_to_extract, dest_dir)
            elif ext == '.sz':
                import cramjam
                # Snappy decompression
                with open(archive_path, 'rb') as f_in:
                    compressed_data = f_in.read()
                    
                    decompress_success = False
                    data = None

                    # 1. Try cramjam (raw/framed)
                    try:
                         data = cramjam.snappy.decompress(compressed_data)
                         decompress_success = True
                    except Exception:
                         pass
                    
                    # 2. Try cramjam raw if previous failed (sometimes api differs)
                    if not decompress_success:
                        try:
                            data = cramjam.snappy.decompress_raw(compressed_data)
                            decompress_success = True
                        except Exception:
                            pass
                            
                    if decompress_success:
                        out_path = os.path.join(dest_dir, file_to_extract)
                        with open(out_path, 'wb') as f_out:
                            f_out.write(data)
                    else:
                         # 3. Fallback: Maybe it's NOT snappy? (e.g. 7z named as .sz)
                         # Check for 7z signature: '7' 'z' 0xBC 0xAF 0x27 0x1C
                         is_7z = False
                         if len(compressed_data) > 6:
                             if compressed_data[:6] == b'\x37\x7a\xbc\xaf\x27\x1c':
                                 is_7z = True
                         
                         if is_7z:
                             # Use py7zr
                             try:
                                 import py7zr
                                 with py7zr.SevenZipFile(archive_path, mode='r') as z:
                                     # .sz usually implies single file, but if it's 7z, use the target file naming
                                     # If file_to_extract match what's inside (which we guessed in list_files as basename), we are good.
                                     # But if it's a full 7z, our list_files for .sz guessed wrong!
                                     # But wait, list_files for .sz returned [basename].
                                     # If the file is 7z, py7zr extraction needs usually a target.
                                     # If we list all, we might find the real name.
                                     # But here we are in extract.
                                     # Let's extract all.
                                     z.extractall(path=dest_dir)
                                     # Then rename if needed? 
                                     # Or just return the extracted file if it matches expected or is the only one.
                                     extracted = os.listdir(dest_dir)
                                     # If there is one file, assuming it's it.
                             except Exception as e:
                                 logger.error(f"py7zr failed on .sz file: {e}")
                                 # Last resort patool
                                 import patoolib
                                 patoolib.extract_archive(archive_path, outdir=dest_dir)
                         else:
                             # Last resort patool (likely for handling framed snappy via snzip)
                             import patoolib
                             patoolib.extract_archive(archive_path, outdir=dest_dir)

            else:
                # Fallback to patool
                import patoolib
                patoolib.extract_archive(archive_path, outdir=dest_dir)
                
            full_path = os.path.join(dest_dir, file_to_extract)
            
            # Verify if expected file exists
            if not os.path.exists(full_path):
                # If extraction succeeded but filename is different (e.g. .sz removed ext, or inner 7z had different name)
                # Check what IS in the folder
                extracted_files = os.listdir(dest_dir)
                if extracted_files:
                    # If we expected a specific file but it's not there, maybe it's the only file there?
                    if len(extracted_files) == 1:
                         full_path = os.path.join(dest_dir, extracted_files[0])
                    else:
                         # Try to find a partial match or just pick first likely candidate
                         # For now, let's just pick the first file that looks like SCL, or just first file
                         candidates = [f for f in extracted_files if f.lower().endswith(('.scd', '.cid', '.icd', '.xml'))]
                         if candidates:
                             full_path = os.path.join(dest_dir, candidates[0])
                         else:
                             full_path = os.path.join(dest_dir, extracted_files[0])
            
            return full_path
        except Exception as e:
            logger.error(f"Failed to extract {file_to_extract}: {e}")
            raise

    @staticmethod
    def extract_all(archive_path: str, dest_dir: str) -> None:
        """Extract entire archive to dest_dir."""
        _, ext = os.path.splitext(archive_path.lower())

        try:
            if ext == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(dest_dir)
            elif ext in ('.tar', '.gz', '.tgz'):
                with tarfile.open(archive_path, 'r') as tf:
                    tf.extractall(dest_dir)
            elif ext == '.7z':
                import py7zr
                with py7zr.SevenZipFile(archive_path, mode='r') as z:
                    z.extractall(path=dest_dir)
            elif ext == '.rar':
                import rarfile
                with rarfile.RarFile(archive_path) as rf:
                    rf.extractall(dest_dir)
            elif ext == '.sz':
                # Try to extract as snappy single-file first
                try:
                    import cramjam
                    with open(archive_path, 'rb') as f_in:
                        compressed_data = f_in.read()
                    data = None
                    try:
                        data = cramjam.snappy.decompress(compressed_data)
                    except Exception:
                        try:
                            data = cramjam.snappy.decompress_raw(compressed_data)
                        except Exception:
                            data = None
                    if data is not None:
                        base_name = os.path.basename(archive_path)
                        out_name = base_name[:-3] if base_name.lower().endswith('.sz') else base_name + ".decoded"
                        out_path = os.path.join(dest_dir, out_name)
                        with open(out_path, 'wb') as f_out:
                            f_out.write(data)
                        return
                except Exception:
                    pass

                # Fallback to patool or 7z handling
                try:
                    import py7zr
                    with py7zr.SevenZipFile(archive_path, mode='r') as z:
                        z.extractall(path=dest_dir)
                except Exception:
                    import patoolib
                    patoolib.extract_archive(archive_path, outdir=dest_dir)
            else:
                import patoolib
                patoolib.extract_archive(archive_path, outdir=dest_dir)
        except Exception as e:
            logger.error(f"Failed to extract archive {archive_path}: {e}")
            raise
