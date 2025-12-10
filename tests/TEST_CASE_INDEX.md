# PropTalk Test Case Index

## Backend Test Cases

### Authentication Module
- **TC-001**: Admin Login with Valid Credentials
- **TC-002**: Admin Login with Invalid Email
- **TC-003**: Admin Login with Invalid Password
- **TC-004**: Admin Login with Missing Email
- **TC-005**: Admin Login with Missing Password
- **TC-006**: Get Current Admin with Valid Token
- **TC-007**: Get Current Admin with Invalid Token
- **TC-008**: Get Current Admin without Token
- **TC-009**: Real Estate Agent Login with Valid Credentials
- **TC-010**: Token Format Validation

### Call Management Module
- **TC-011**: Initiate Single Call with Valid Parameters
- **TC-012**: Initiate Call with Invalid Phone Number Format
- **TC-013**: Initiate Call without Authentication
- **TC-014**: Initiate Batch Calls with Valid Parameters
- **TC-015**: Initiate Batch Calls with Empty Contact List
- **TC-016**: Retrieve Call History with Pagination
- **TC-017**: Retrieve Call History with Invalid Page Number
- **TC-018**: Retrieve Specific Call by ID
- **TC-019**: Retrieve Call with Non-Existent ID
- **TC-020**: Retrieve Call Statistics for Agent
- **TC-021**: Retrieve Call Statistics for Admin
- **TC-022**: Retrieve Call Recording URL
- **TC-023**: Retrieve Call Transcript
- **TC-024**: Twilio Voice Webhook Handler
- **TC-025**: Twilio Status Callback Webhook

### Property Management Module
- **TC-026**: Create Property with Valid Data
- **TC-027**: Create Property with Missing Required Fields
- **TC-028**: Create Property with Invalid Data Types
- **TC-029**: Retrieve All Properties with Pagination
- **TC-030**: Retrieve Property by ID
- **TC-031**: Filter Properties by Bedrooms
- **TC-032**: Filter Properties by Price Range
- **TC-033**: Update Property with Valid Data
- **TC-034**: Update Non-Existent Property
- **TC-035**: Delete Property

### Contact Management Module
- **TC-036**: Create Contact with Valid Data
- **TC-037**: Create Contact with Invalid Email Format
- **TC-038**: Create Contact with Invalid Phone Number Format
- **TC-039**: Retrieve All Contacts with Pagination
- **TC-040**: Retrieve Contact by ID
- **TC-041**: Search Contacts by Name
- **TC-042**: Update Contact with Valid Data
- **TC-043**: Link Contact to Property
- **TC-044**: Delete Contact
- **TC-045**: Retrieve Contacts Linked to Property

### Voice Agent Management Module
- **TC-046**: Create Voice Agent Request
- **TC-047**: Retrieve Voice Agent Request Status
- **TC-048**: Admin Retrieve Pending Voice Agent Requests
- **TC-049**: Admin Approve Voice Agent Request
- **TC-050**: Admin Reject Voice Agent Request
- **TC-051**: Retrieve Voice Agent Configuration
- **TC-052**: Update Voice Agent Configuration
- **TC-053**: Activate Voice Agent
- **TC-054**: Deactivate Voice Agent
- **TC-055**: Retrieve Voice Agent Status

### Document Management Module
- **TC-056**: Upload CSV Document with Valid Format
- **TC-057**: Upload Document with Invalid File Type
- **TC-058**: Upload Document without File
- **TC-059**: Retrieve Uploaded Documents List
- **TC-060**: Retrieve Document Parsing Results

## Frontend Test Cases

### Authentication Module
- **TC-061**: Admin Login Form Rendering
- **TC-062**: Admin Login with Valid Credentials
- **TC-063**: Admin Login with Invalid Credentials
- **TC-064**: Agent Login Form Rendering
- **TC-065**: Agent Login with Valid Credentials
- **TC-066**: Form Validation for Empty Email Field
- **TC-067**: Form Validation for Empty Password Field
- **TC-068**: Email Format Validation
- **TC-069**: Loading State During Authentication
- **TC-070**: Session Persistence After Login

### Property Management Module
- **TC-071**: Property List Rendering
- **TC-072**: Create Property Form Rendering
- **TC-073**: Create Property with Valid Data
- **TC-074**: Filter Properties by Bedrooms
- **TC-075**: Filter Properties by Price Range
- **TC-076**: Edit Property Form Rendering
- **TC-077**: Update Property with Valid Data
- **TC-078**: Delete Property Confirmation
- **TC-079**: Property Search Functionality
- **TC-080**: Property Details View

### Call Management Module
- **TC-081**: Call History List Rendering
- **TC-082**: Initiate Single Call
- **TC-083**: Initiate Batch Calls
- **TC-084**: Call Status Display
- **TC-085**: Call Duration Formatting
- **TC-086**: Call Recording Playback
- **TC-087**: Call Transcript Display
- **TC-088**: Filter Calls by Status
- **TC-089**: Call Statistics Display
- **TC-090**: Call Details View

## Total Test Cases

- **Backend**: 60 test cases (TC-001 to TC-060)
- **Frontend**: 30 test cases (TC-061 to TC-090)
- **Total**: 90 test cases

## Test Execution

### Backend Tests
```bash
cd PropTalk-Backend
pytest tests/ -v
```

### Frontend Tests
```bash
cd PropTalk-Frontend
npm test
```

## Notes for Documentation

- All test cases are numbered sequentially for easy reference
- Test descriptions are written in academic style suitable for FYP reports
- Test output is formatted for screenshot capture
- Each test module covers a complete functional area
- Test IDs can be easily referenced in documentation and presentations
