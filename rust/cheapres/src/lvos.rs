use std::collections::HashMap;
use regex::Regex;

pub mod lvos
{
	
	
	pub struct Lvo
   {
	   entity_type : std::collections::HashMap<String,String>,
	   libname2handle : std::collections::HashMap<String,String>,
	   libname2libstr : std::collections::HashMap<String,String>,
	   offset_name : std::collections::HashMap<(String,i32),String>,
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
		  let lvo_re = regex::Regex::new(r"\*+\sLVOs for (.*)\.(library|resource)").unwrap();
		  let eq_re = regex::Regex::new(r"(\w+)\s+equ\s+(-\d+)").unwrap();
		  let lvo_lines = std::str::from_utf8(include_bytes!("LVOs.i")).unwrap().lines();
		
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
}
