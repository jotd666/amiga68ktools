use std::collections::HashMap;
use regex::Regex;

pub mod input_files
{
   const EQU_RE_STRING : &str = r"(\w+)\s+equ\s+(-\d+)";
	
   pub struct Lvo
   {
	   entity_type : std::collections::HashMap<String,String>,
	   libname2handle : std::collections::HashMap<String,String>,
	   libname2libstr : std::collections::HashMap<String,String>,
	   offset_name : std::collections::HashMap<(String,i32),String>,
 
    }
   
   fn build_regex(s : &str) -> regex::Regex
   {
	   regex::Regex::new(s).unwrap()
   }
   fn build_regex_ci(s : &str) -> regex::Regex
   {
	   regex::Regex::new(&format!("(?i){s}")[..]).unwrap()
   }
   
  impl Lvo
   {
	fn capitalize(s: &str) -> String {
			let mut c = s.chars();
			match c.next() {
				None => String::new(),
				Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
			}
		}
		
	  pub fn new() -> Lvo
	  {

		  let lvo_lines = std::str::from_utf8(include_bytes!("LVOs.i")).unwrap().lines();
		  let lvo_re = build_regex(r"\*+\sLVOs for (.*)\.(library|resource)");
		  let eq_re = build_regex(EQU_RE_STRING);
		
		  let mut rval = Lvo{
			  entity_type : std::collections::HashMap::new(),
			  offset_name : std::collections::HashMap::new(),
			  libname2handle : std::collections::HashMap::new(),
			  libname2libstr : std::collections::HashMap::new(),
		  };

		  let mut libname = "";
		  let mut libtype = "";
		  
		  // populate the entity types
		  for line in lvo_lines
		  {
			  if let Some(caps) = lvo_re.captures(line) {
				  libname = caps.get(1).map_or("", |m| m.as_str());
				  libtype = caps.get(2).map_or("", |m| m.as_str());
				  rval.entity_type.insert(libname.to_string(),libtype.to_string());
				  
			  } else if let Some(caps) = eq_re.captures(line) {
				  let funcname = caps.get(1).map_or("", |m| m.as_str()).to_string();
				  let funcoffset = caps.get(2).map_or("", |m| m.as_str()).parse::<i32>().unwrap();
				  rval.offset_name.insert((libname.to_string(),funcoffset),funcname);
			  }
		  }
		  // in the end create some aux mappings
		  for ((key,_), _) in &rval.offset_name {
			  let prefix = Self::capitalize(&key);
			  // would be better to use &key as key lifetime is the same as the Lvo object
			  // that would save some memory but lifetimes are beyond me ATM
			  rval.libname2handle.insert(key.to_string(),format!("{}Base",prefix));
			  rval.libname2libstr.insert(key.to_string(),format!("{}Name",prefix));
		  }
		  
		  rval
	  }
   }
   
   pub struct AsmFile
   {
    execcopy_re    : regex::Regex,
    lab_re          : regex::Regex,
    labeldecl_re     : regex::Regex,
    leahardbase_re   : regex::Regex,
    movehardbase_re : regex::Regex,
    set_ax_re        : regex::Regex,
    syscall_re       : regex::Regex,
    syscall_re2      : regex::Regex,
    syscall_re3       : regex::Regex,
    valid_base        : regex::Regex,
    address_reg_re    : regex::Regex,
    return_re         : regex::Regex,
    ax_di_re           : regex::Regex,
    ax_di_re_2         : regex::Regex,
    hexdata_re           : regex::Regex,
	   
	   
   }
   
   impl AsmFile
   {
	   pub fn load(input_file : &String) -> AsmFile
	   {
		   let mut rval = AsmFile{
			execcopy_re     : build_regex_ci(r"MOVE.*ABSEXECBASE.*,(LAB_....)\s"),
			lab_re          : build_regex_ci(r"(LAB_....|ABSEXECBASE)"),
			labeldecl_re    : build_regex_ci(r"(LAB_....):"),
			leahardbase_re  : build_regex_ci(r"LEA\s+HARDBASE,A([0-6])"),
			movehardbase_re : build_regex_ci(r"MOVEA?.L\s+#\$0*DFF000,A([0-6])"),
			set_ax_re       : build_regex_ci(r"MOVEA?\.L\s+([\S]+),A([0-6])\s"),
			syscall_re      : build_regex_ci(r"(JMP|JSR)\s+(-\d+)\(A6\)"),
			syscall_re2     : build_regex_ci(r"(JMP|JSR)\s+\((-\d+),A6\)"),
			syscall_re3     : build_regex_ci(r"(JMP|JSR)\s+(-\$[\dA-F]+)\(A6\)"),
			valid_base      : build_regex_ci(r"([\-\w]{3,}(\(A\d\))?)"),
			address_reg_re  : build_regex_ci(r"A([0-6])"),
			return_re       : build_regex_ci(r"\b(RT[SED])\b"),
			ax_di_re        : build_regex_ci(r"([\s,])(\$[0-9A-F]+|\d+)\(A([0-6])\)"),
			ax_di_re_2      : build_regex_ci(r"([\s,])\((\$[0-9A-F]+|\d+),A([0-6])\)"),
			hexdata_re      : build_regex_ci(r"(?:.*;.*:\s+|DC.[WLB]\s+\$)([A-F\d]+)"),
		   };
		  
		  rval
		   
	   }
   }
}
