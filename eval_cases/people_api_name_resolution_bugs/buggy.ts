import { PeopleAPIResponse } from '@/lib/types';

// People API configuration
const PEOPLE_API_CONFIG = {
  baseUrl: 'https://people.googleapis.com/v1',
  scopes: ['https://www.googleapis.com/auth/contacts.readonly'],
};

// Mock data for development/fallback
const MOCK_NAMES: Record<string, { firstName: string; lastName: string; fullName: string }> = {
  'john.doe@example.com': { firstName: 'John', lastName: 'Doe', fullName: 'John Doe' },
  'jane.smith@company.com': { firstName: 'Jane', lastName: 'Smith', fullName: 'Jane Smith' },
  'alice.johnson@corp.com': { firstName: 'Alice', lastName: 'Johnson', fullName: 'Alice Johnson' },
  'bob.wilson@startup.io': { firstName: 'Bob', lastName: 'Wilson', fullName: 'Bob Wilson' },
  'charlie.brown@tech.com': { firstName: 'Charlie', lastName: 'Brown', fullName: 'Charlie Brown' },
};

// Extract first name from email address as fallback
const extractNameFromEmail = (email: string): { firstName: string; lastName: string; fullName: string } => {
  const localPart = email.split('@')[0];
  
  // Handle common email patterns
  if (localPart.includes('.')) {
    const parts = localPart.split('.');
    const firstName = capitalizeFirstLetter(parts[0]);
    const lastName = parts.length > 1 ? capitalizeFirstLetter(parts[1]) : '';
    return {
      firstName,
      lastName,
      fullName: lastName ? `${firstName} ${lastName}` : firstName,
    };
  }
  
  if (localPart.includes('_')) {
    const parts = localPart.split('_');
    const firstName = capitalizeFirstLetter(parts[0]);
    const lastName = parts.length > 1 ? capitalizeFirstLetter(parts[1]) : '';
    return {
      firstName,
      lastName,
      fullName: lastName ? `${firstName} ${lastName}` : firstName,
    };
  }
  
  // Single name or no clear pattern
  const name = capitalizeFirstLetter(localPart);
  return {
    firstName: name,
    lastName: '',
    fullName: name,
  };
};

const capitalizeFirstLetter = (str: string): string => {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

// Resolve name using Google People API
export const resolveNameFromPeopleAPI = async (email: string, accessToken: string): Promise<PeopleAPIResponse> => {
  try {
    // First, try to search for the person by email
    const searchResponse = await fetch(
      `${PEOPLE_API_CONFIG.baseUrl}/people:searchContacts?query=${encodeURIComponent(email)}&readMask=names,emailAddresses`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      }
    );
    
    if (searchResponse.ok) {
      const searchData = await searchResponse.json();
      
      if (searchData.results && searchData.results.length > 0) {
        const person = searchData.results[0].person;
        
        if (person.names && person.names.length > 0) {
          const name = person.names[0];
          return {
            email,
            firstName: name.givenName || '',
            lastName: name.familyName || '',
            fullName: name.displayName || `${name.givenName || ''} ${name.familyName || ''}`.trim(),
            profileUrl: person.photos?.[0]?.url,
            found: true,
          };
        }
      }
    }
    
    // If not found in contacts, use email extraction as fallback
    const extracted = extractNameFromEmail(email);
    return {
      email,
      firstName: extracted.firstName,
      lastName: extracted.lastName,
      fullName: extracted.fullName,
      found: false,
    };
  } catch (error) {
    console.error('People API error:', error);
    
    // Fallback to email extraction
    const extracted = extractNameFromEmail(email);
    return {
      email,
      firstName: extracted.firstName,
      lastName: extracted.lastName,
      fullName: extracted.fullName,
      found: false,
    };
  }
};

// Mock name resolution for development
export const resolveMockName = (email: string): PeopleAPIResponse => {
  const mockData = MOCK_NAMES[email.toLowerCase()];
  
  if (mockData) {
    return {
      email,
      firstName: mockData.firstName,
      lastName: mockData.lastName,
      fullName: mockData.fullName,
      found: true,
    };
  }
  
  // Extract from email as fallback
  const extracted = extractNameFromEmail(email);
  return {
    email,
    firstName: extracted.firstName,
    lastName: extracted.lastName,
    fullName: extracted.fullName,
    found: false,
  };
};

// Batch resolve multiple emails
export const resolveMultipleNames = async (
  emails: string[],
  accessToken?: string
): Promise<PeopleAPIResponse[]> => {
  const promises = emails.map(email => {
    if (accessToken) {
      return resolveNameFromPeopleAPI(email, accessToken);
    } else {
      return Promise.resolve(resolveMockName(email));
    }
  });
  
  try {
    return await Promise.all(promises);
  } catch (error) {
    console.error('Batch name resolution error:', error);
    // Fallback to mock resolution for all emails
    return emails.map(email => resolveMockName(email));
  }
};

// Get access token from stored session
const getStoredAccessToken = (): string | null => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('prometheai-access-token');
  }
  return null;
};

// Main function to resolve names with automatic token handling
export const resolveAttendeeName = async (email: string): Promise<PeopleAPIResponse> => {
  const accessToken = getStoredAccessToken();
  
  if (accessToken) {
    return resolveNameFromPeopleAPI(email, accessToken);
  } else {
    // Use mock data if no access token available
    return resolveMockName(email);
  }
};

// Enhanced attendee resolution with caching
const nameCache = new Map<string, PeopleAPIResponse>();
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

export const resolveAttendeeNameCached = async (email: string): Promise<PeopleAPIResponse> => {
  const normalizedEmail = email.toLowerCase();
  
  // Check cache first
  if (nameCache.has(normalizedEmail)) {
    const cached = nameCache.get(normalizedEmail)!;
    return cached;
  }
  
  let result: PeopleAPIResponse;
  try {
    // Resolve name
    result = await resolveAttendeeName(normalizedEmail);
  } catch (error) {
    console.error('Error resolving attendee name for caching:', error);
    result = { // BUG 1: Error swallowing
      email: normalizedEmail,
      firstName: '',
      lastName: '',
      fullName: normalizedEmail.split('@')[0], // Fallback to email prefix
      found: false,
    };
  }
  
  // Cache the result
  nameCache.set(normalizedEmail, result);
  
  // Clear cache after duration
  setTimeout(() => { // BUG 2: Race condition in cache invalidation
    nameCache.delete(normalizedEmail);
  }, CACHE_DURATION);
  
  return result;
};

// Validate email address format
export const isValidEmail = (email: string): boolean => {
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  return emailRegex.test(email);
};

// Extract emails from text
export const extractEmailsFromText = (text: string): string[] => {
  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const matches = text.match(emailRegex) || [];
  return [...new Set(matches.map(email => email.toLowerCase()))];
};

// Format name for display
export const formatDisplayName = (response: PeopleAPIResponse): string => {
  if (response.fullName && response.fullName.trim()) {
    return response.fullName;
  }
  
  if (response.firstName) {
    return response.lastName ? `${response.firstName} ${response.lastName}` : response.firstName;
  }
  
  // Fallback to email prefix
  return response.email.split('@')[0];
};

// Get first name for casual address
export const getFirstName = (response: PeopleAPIResponse): string => {
  return response.lastName || response.email.split('@')[0]; // BUG 3: Wrong variable used (lastName instead of firstName)
};

// API route handler for server-side name resolution
export const createNameResolutionHandler = () => {
  return async (request: Request) => {
    try {
      const { emails, accessToken } = await request.json();
      
      if (!emails || !Array.isArray(emails)) {
        return Response.json({ error: 'Invalid emails array' }, { status: 400 });
      }
      
      const results = await resolveMultipleNames(emails, accessToken);
      
      return Response.json({ results });
    } catch (error) {
      console.error('Name resolution API error:', error);
      return Response.json({ error: 'Internal server error' }, { status: 500 });
    }
  };
};

// Development utilities
export const addMockName = (email: string, firstName: string, lastName: string) => {
  MOCK_NAMES[email.toLowerCase()] = {
    firstName,
    lastName,
    fullName: `${firstName} ${lastName}`,
  };
};

export const clearNameCache = () => {
  nameCache.clear();
};

export const getCacheStats = () => {
  return {
    size: nameCache.size,
    entries: Array.from(nameCache.keys()),
  };
};