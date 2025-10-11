import os
from typing import Dict, Optional
from livekit.agents import function_tool, RunContext


class InstructionLoader:
    """Loads instruction flows dynamically based on customer intent"""
    
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        self.instructions_dir = os.path.join(project_root, 'data', 'Instructions')
        
        # Mapping between intents and instruction files (OPTIMIZED versions)
        self.intent_to_file = {
            'KYC_APPROVAL': 'Enhanced_KYC_Approval_Contractor.txt',
            'POINT_REDEMPTION': 'Unable_to_redeem_points.txt', 
            'QR_SCANNING': 'QR_Scanning_Merged.txt',
            'ACCOUNT_BLOCKED': 'Painter_Contractor_Account_Blocked.txt',
            'UNCLEAR': None
        }
        
        self.scenario_to_file = {
            'KYC_PENDING': 'Enhanced_KYC_Approval_Contractor.txt',
            'INVALID_BARCODE': 'QR_Scanning_Merged.txt',
            'ENHANCED_KYC': 'Enhanced_KYC_Approval_Contractor.txt'
        }
    
    def load_instruction_file(self, filename: str) -> Optional[str]:
        """
        Load instruction content from file
        
        Args:
            filename: Name of the instruction file to load
            
        Returns:
            File content as string, or None if file not found
        """
        if not filename:
            return None
            
        file_path = os.path.join(self.instructions_dir, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            print(f"Warning: Instruction file {filename} not found at {file_path}")
            return None
        except Exception as e:
            print(f"Error loading instruction file {filename}: {str(e)}")
            return None
    
    def get_instruction_for_intent(self, intent: str, scenario: Optional[str] = None) -> Optional[str]:
        """
        Get instruction content for a specific intent
        
        Args:
            intent: Customer intent (KYC_APPROVAL, POINT_REDEMPTION, etc.)
            scenario: Optional specific scenario within the intent
            
        Returns:
            Instruction content as string
        """
        # First check for specific scenario
        if scenario and scenario in self.scenario_to_file:
            filename = self.scenario_to_file[scenario]
            content = self.load_instruction_file(filename)
            if content:
                return content
        
        # Fall back to general intent mapping
        filename = self.intent_to_file.get(intent)
        if filename:
            return self.load_instruction_file(filename)
        
        return None
    
    def list_available_instructions(self) -> Dict:
        """
        List all available instruction files
        
        Returns:
            Dictionary of available instructions with their descriptions
        """
        available_files = {}
        
        if os.path.exists(self.instructions_dir):
            for filename in os.listdir(self.instructions_dir):
                if filename.endswith('.txt'):
                    file_path = os.path.join(self.instructions_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            # Read first few lines to get description
                            first_lines = []
                            for i, line in enumerate(f):
                                if i >= 3:  # Read first 3 lines
                                    break
                                first_lines.append(line.strip())
                        
                        available_files[filename] = {
                            'description': ' '.join(first_lines),
                            'path': file_path
                        }
                    except Exception as e:
                        available_files[filename] = {
                            'description': f'Error reading file: {str(e)}',
                            'path': file_path
                        }
        
        return available_files


# Initialize loader instance (singleton)
_instruction_loader = InstructionLoader()


def load_instructions_for_intent_func(intent: str, scenario: Optional[str] = None) -> Dict:
    """
    Load the appropriate instruction flow based on customer intent.
    
    This tool loads the specific instruction file that the agent should follow
    based on the customer's identified intent.
    
    Args:
        intent: The customer intent (KYC_APPROVAL, POINT_REDEMPTION, QR_SCANNING, ACCOUNT_BLOCKED)
        scenario: Optional specific scenario for more targeted instructions
        
    Returns:
        Dictionary containing:
        - intent: The intent being handled
        - scenario: The specific scenario (if provided)
        - instructions: The full instruction content to follow
        - filename: The instruction file that was loaded
        - available: Whether instructions were found
        - summary: Brief summary of what these instructions cover
    """
    
    instructions = _instruction_loader.get_instruction_for_intent(intent, scenario)
    filename = None
    
    # Determine which file was loaded
    if scenario and scenario in _instruction_loader.scenario_to_file:
        filename = _instruction_loader.scenario_to_file[scenario]
    elif intent in _instruction_loader.intent_to_file:
        filename = _instruction_loader.intent_to_file[intent]
    
    # Create summary based on intent
    summaries = {
        'KYC_APPROVAL': 'Instructions for handling KYC approval and contractor verification issues',
        'POINT_REDEMPTION': 'Instructions for handling point redemption and cash withdrawal issues', 
        'QR_SCANNING': 'Instructions for handling QR code scanning and barcode related issues',
        'ACCOUNT_BLOCKED': 'Instructions for handling account blocking and access issues',
        'UNCLEAR': 'No specific instructions - use general inquiry approach'
    }
    
    return {
        'intent': intent,
        'scenario': scenario,
        'instructions': instructions,
        'filename': filename,
        'available': instructions is not None,
        'summary': summaries.get(intent, 'Unknown intent type'),
        'instructions_length': len(instructions) if instructions else 0
    }


def get_available_instruction_flows_func() -> Dict:
    """
    Get list of all available instruction flows.
    
    Returns:
        Dictionary with all available instruction files and their descriptions
    """
    
    available = _instruction_loader.list_available_instructions()
    
    # Add intent mapping information
    intent_mapping = {}
    for intent, filename in _instruction_loader.intent_to_file.items():
        if filename:
            intent_mapping[intent] = filename
    
    scenario_mapping = _instruction_loader.scenario_to_file
    
    return {
        'available_files': available,
        'intent_mapping': intent_mapping,
        'scenario_mapping': scenario_mapping,
        'instructions_directory': _instruction_loader.instructions_dir,
        'total_files': len(available)
    }


def validate_instruction_files_func() -> Dict:
    """
    Validate that all required instruction files exist and are readable.
    
    Returns:
        Dictionary with validation results for each expected instruction file
    """
    
    validation_results = {}
    
    # Check intent-based files
    for intent, filename in _instruction_loader.intent_to_file.items():
        if filename:
            content = _instruction_loader.load_instruction_file(filename)
            validation_results[f"intent_{intent}"] = {
                'filename': filename,
                'exists': content is not None,
                'size': len(content) if content else 0,
                'status': 'OK' if content else 'MISSING'
            }
    
    # Check scenario-based files
    for scenario, filename in _instruction_loader.scenario_to_file.items():
        content = _instruction_loader.load_instruction_file(filename)
        validation_results[f"scenario_{scenario}"] = {
            'filename': filename,
            'exists': content is not None,
            'size': len(content) if content else 0,
            'status': 'OK' if content else 'MISSING'
        }
    
    # Overall status
    all_ok = all(result['status'] == 'OK' for result in validation_results.values())
    
    return {
        'overall_status': 'ALL_OK' if all_ok else 'SOME_MISSING',
        'details': validation_results,
        'instructions_directory': _instruction_loader.instructions_dir
    }

@function_tool()
async def load_instructions_for_intent(context: RunContext, intent: str, scenario: str = None) -> dict:
    """Load the appropriate instruction flow based on customer intent."""
    return load_instructions_for_intent_func(intent, scenario)

@function_tool()
async def get_available_instruction_flows(context: RunContext) -> dict:
    """Get list of all available instruction flows."""
    return get_available_instruction_flows_func()